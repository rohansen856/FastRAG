#!/usr/bin/env python
"""Index FastRAG's own documentation and source, so it can answer questions about itself.

The alternative corpus to `scripts/ingest-msmarco.py`. Where that one gets its
golden labels free from MS MARCO's `is_selected` column, this one has to derive
them, and the derivation is the interesting part:

* The generator writes the questions; it never picks the labels.
  `relevant_chunk_ids` come from the chunker's own output for the section each
  question was written from, so a label cannot drift from what was indexed.
* Unanswerable items are verified against the *built index* rather than trusted.
  A file exclusion is not a semantic exclusion - this repository documents itself
  twice, and a module docstring will happily answer a question written from a
  held-out doc.
* The prose docs are translated into five Indic languages, because the `language`
  payload filter, the six-language golden split and `FASTRAG_GUARDRAIL_LANGUAGES`
  all assume chunks exist in each. MSMARCO-XI is itself a machine translation of
  MS MARCO, so this is the same bargain.

Ordering matters and is enforced below: chunks must exist before labels can name
them, and the index must exist before an unanswerable can be verified. Prefer
`--no-activate` when re-ingesting against a live deployment; see `docs/self-corpus.md`.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from selfcorpus import golden as golden_mod  # noqa: E402
from selfcorpus import sources, translate  # noqa: E402

from fastrag.chunking import build_strategy, chunk_document  # noqa: E402
from fastrag.config import Settings  # noqa: E402
from fastrag.jobs import build_index_builder  # noqa: E402
from fastrag.registry import PostgresIndexRegistry  # noqa: E402

DEFAULT_LANGUAGES = ["hi", "bn", "ta", "te", "mr"]


async def build_chunks(
    documents: list[Any], strategy_names: list[str], embedder: Any, settings: Settings
) -> list[dict[str, Any]]:
    """Chunk every document under every strategy, deduped.

    Deduplication happens here rather than after handing the list to the builder
    because `IndexBuilder._validate_collection` asserts the indexed point count
    equals `len(chunks)` exactly.
    """
    strategies = [
        build_strategy(
            name,
            embedder=embedder,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        for name in strategy_names
    ]
    chunks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        for payload in await chunk_document(document, strategies):
            if payload["chunk_id"] in seen:
                continue
            seen.add(payload["chunk_id"])
            chunks.append(payload)
    return chunks


def content_digest(documents: list[Any]) -> str:
    digest = hashlib.sha256()
    for document in sorted(documents, key=lambda item: item.document_id):
        digest.update(document.document_id.encode())
        digest.update(document.text.encode())
        digest.update((document.language or "").encode())
    return digest.hexdigest()


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def assert_labels_indexed(rows: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> None:
    """Every label must name a chunk that is actually in the collection.

    `scripts/check-golden.py` cannot do this - it validates the schema and has no
    chunk set. Without this a silent chunking change turns recall@20 to zero and
    the failure looks like a retrieval regression.
    """
    indexed = {str(chunk["chunk_id"]) for chunk in chunks}
    missing = {
        chunk_id
        for row in rows
        for chunk_id in row["relevant_chunk_ids"]
        if chunk_id not in indexed
    }
    if missing:
        raise SystemExit(
            f"{len(missing)} golden chunk ids are not in the built index "
            f"(e.g. {sorted(missing)[:3]}); labels and chunks are out of sync"
        )


async def build(args: argparse.Namespace) -> int:
    settings = Settings()
    root = sources.repo_root()
    commit = sources.git_commit(root)

    strategy_names = args.strategies or settings.chunk_strategy_list or ["sentence"]
    golden_strategy = args.golden_strategy or strategy_names[0]
    if golden_strategy != strategy_names[0]:
        # `evaluation.collect_records` and `calibrate.run` both retrieve with
        # chunk_strategy_list[0]; labels against any other strategy score zero.
        raise SystemExit(
            f"--golden-strategy must be the first configured strategy "
            f"({strategy_names[0]!r}), got {golden_strategy!r}"
        )
    if golden_strategy in {"semantic", "metadata_aware"}:
        # `semantic` derives boundaries from float embeddings, so ids move with
        # numerical noise; `metadata_aware` hashes the title into the chunk text,
        # so ids move when a file is renamed. Neither survives as a label.
        raise SystemExit(f"{golden_strategy!r} produces unstable chunk ids; use 'sentence'")

    from fastrag.bootstrap import build_embedder_and_reranker, build_generator

    embedder, reranker = build_embedder_and_reranker(settings)
    generator = build_generator(settings)

    files = sources.load_repo_files(root)
    documents = sources.build_documents(files, commit, site_url=args.site_url)
    print(f"{len(files)} files -> {len(documents)} English documents", flush=True)

    languages = [code.strip() for code in (args.languages or "").split(",") if code.strip()]
    prose = [
        document
        for document in documents
        if document.metadata.get("category") == "documentation"
    ]
    if args.max_translation_sections and len(prose) > args.max_translation_sections:
        # Strided, so a capped run still spans every document rather than
        # translating the first file exhaustively and none of the rest.
        stride = max(1, len(prose) // args.max_translation_sections)
        prose = prose[::stride][: args.max_translation_sections]
    if languages:
        print(
            f"translating {len(prose)} prose sections into {', '.join(languages)}...",
            flush=True,
        )
        failures: list[str] = []
        translated = await translate.translate_documents(
            generator,
            prose,
            root=root,
            languages=languages,
            refresh=args.refresh_translations,
            on_error=lambda key, language, exc: failures.append(f"{language} {key}: {exc}"),
        )
        documents.extend(translated)
        report_failures("document translation", failures)
        print(f"{len(documents)} documents across {1 + len(languages)} languages", flush=True)

    chunks = await build_chunks(documents, strategy_names, embedder, settings)
    if args.max_chunks and len(chunks) > args.max_chunks:
        raise SystemExit(
            f"{len(chunks)} chunks exceeds --max-chunks {args.max_chunks}; "
            "reduce --strategies or raise the cap"
        )
    by_strategy = Counter(str(chunk["strategy"]) for chunk in chunks)
    by_language = Counter(str(chunk["language"]) for chunk in chunks)
    print(f"{len(chunks)} chunks: {dict(by_strategy)}", flush=True)
    print(f"languages: {dict(by_language)}", flush=True)

    # document_id is language-scoped; the key is not, so one lookup serves every
    # language once the chunks are filtered to it.
    key_by_id = {
        document.document_id: str(document.metadata["document_key"])
        for document in documents
    }
    chunk_index = golden_mod.chunk_ids_by_document(
        chunks, golden_strategy, key_by_id, language="en"
    )
    english = [document for document in documents if document.language == "en"]

    print("generating questions...", flush=True)
    qa_failures: list[str] = []
    answerable = await golden_mod.generate_answerable(
        generator,
        english,
        chunk_index,
        limit=args.max_questions,
        priority_keys={
            str(document.metadata["document_key"])
            for document in documents
            if document.language != "en"
        },
        on_error=lambda title, exc: qa_failures.append(f"{title}: {exc}"),
    )
    unanswerable = await golden_mod.generate_unanswerable(
        generator,
        per_topic=args.per_topic,
        on_error=lambda topic, exc: qa_failures.append(f"{topic}: {exc}"),
    )
    print(f"{len(answerable)} answerable, {len(unanswerable)} unanswerable (English)", flush=True)
    report_failures("question generation", qa_failures)

    if args.dry_run:
        print(
            json.dumps(
                {
                    "documents": len(documents),
                    "chunks": len(chunks),
                    "chunks_by_strategy": dict(by_strategy),
                    "chunks_by_language": dict(by_language),
                    "answerable": len(answerable),
                    "unanswerable": len(unanswerable),
                },
                indent=2,
            )
        )
        return 0

    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    builder = build_index_builder(settings, registry)
    manifest = await builder.build_from_chunks(
        chunks,
        content_version=content_digest(documents),
        version=args.index_version,
        activate=not args.no_activate,
    )
    print(f"indexed into {manifest.collection_name} (state={manifest.state})", flush=True)
    return await finalise(
        args,
        settings=settings,
        manifest=manifest,
        chunks=chunks,
        key_by_id=key_by_id,
        answerable=answerable,
        unanswerable=unanswerable,
        languages=languages,
        golden_strategy=golden_strategy,
        embedder=embedder,
        reranker=reranker,
        generator=generator,
    )


async def finalise(
    args: argparse.Namespace,
    *,
    settings: Settings,
    manifest: Any,
    chunks: list[dict[str, Any]],
    key_by_id: dict[str, str],
    answerable: list[Any],
    unanswerable: list[Any],
    languages: list[str],
    golden_strategy: str,
    embedder: Any,
    reranker: Any,
    generator: Any,
) -> int:
    """Verify labels against the freshly built collection, then write the eval sets.

    Runs after indexing because an unanswerable can only be verified against a
    real retrieval, and retrieval needs the collection to exist.
    """
    from fastrag.bootstrap import build_retriever

    # Read the new collection by name: under --no-activate the alias still points
    # at the previous corpus.
    retriever = build_retriever(settings)
    collection = manifest.collection_name

    async def retrieve(query: str, vector: list[float], limit: int) -> Any:
        return await retriever.retrieve(
            query, vector, limit, collection=collection, strategy=golden_strategy
        )

    # Where the answerable population actually sits, so "scores like an answer"
    # is measured rather than guessed.
    scores: list[float] = []
    for candidate in answerable:
        vector = await embedder.embed_query(candidate.query)
        ranked = await reranker.rerank(
            candidate.query,
            await retrieve(candidate.query, vector, settings.retrieval_candidate_k),
            settings.retrieval_candidate_k,
        )
        scores.append(ranked[0].score if ranked else float("-inf"))
    finite = sorted(score for score in scores if score > float("-inf"))
    floor = finite[len(finite) // 4] if finite else 0.0
    print(f"answerable top-1 lower quartile: {floor:.4f}", flush=True)

    kept, leaks = await golden_mod.drop_leaking_unanswerables(
        unanswerable,
        embedder=embedder,
        retrieve=retrieve,
        reranker=reranker,
        candidate_k=settings.retrieval_candidate_k,
        answerable_floor=floor,
    )
    print(f"unanswerable: {len(kept)} kept, {len(leaks)} dropped as answerable-in-corpus")
    for query, score in leaks[:5]:
        print(f"  leak ({score:.3f}): {query}")

    pool = list(answerable) + kept
    if languages:
        print("translating questions...", flush=True)
        translated_index = {
            language: golden_mod.chunk_ids_by_document(
                chunks, golden_strategy, key_by_id, language=language
            )
            for language in languages
        }
        translation_failures: list[str] = []
        pool += await golden_mod.translate_questions(
            generator,
            pool,
            translated_index,
            languages=languages,
            on_error=lambda language, exc: translation_failures.append(f"{language}: {exc}"),
        )
        report_failures("question translation", translation_failures)

    # Deduplicate on id: `load_golden` rejects duplicates outright.
    unique = {candidate.id: candidate for candidate in pool}
    pool = sorted(unique.values(), key=lambda item: item.id)

    golden, calibration = golden_mod.split_pool(pool)
    golden_rows = [candidate.as_record() for candidate in golden]
    calibration_rows = [candidate.as_record() for candidate in calibration]

    assert_labels_indexed(golden_rows, chunks)
    assert_labels_indexed(calibration_rows, chunks)
    report_split("golden", golden_rows)
    report_split("calibration", calibration_rows)

    # A paraphrase per calibration item would be hundreds of generator calls for
    # a threshold that needs tens of pairs. Strided rather than sliced: ids sort
    # by language, so the first N items would all be Bengali - which is how the
    # shipped calibration set ended up monolingual in the first place.
    stride = max(1, len(calibration) // max(1, args.cache_pair_samples))
    sample = calibration[::stride][: args.cache_pair_samples]
    paraphrases = await golden_mod.generate_paraphrases(generator, sample)
    pairs = golden_mod.cache_pairs(sample, paraphrases)

    # Validated before anything is written, so a failed run leaves the previous
    # eval sets intact rather than a half-valid one for calibrate to pick up.
    check_minimums(golden_rows, calibration_rows, pairs)

    write_jsonl(args.golden_output, golden_rows)
    write_jsonl(args.calibration_output, calibration_rows)
    write_jsonl(args.cache_pairs_output, pairs)
    print(
        f"wrote {len(golden_rows)} golden, {len(calibration_rows)} calibration, "
        f"{len(pairs)} cache pairs"
    )

    if args.no_activate:
        print(
            "\nCollection built but NOT serving. Calibrate against it, then activate:\n"
            f"  FASTRAG_QDRANT_ALIAS={manifest.collection_name} \\\n"
            "    uv run python -m fastrag.calibrate "
            f"--golden {args.calibration_output} --cache-pairs {args.cache_pairs_output}\n"
            f"  uv run python scripts/ingest-self.py --activate {manifest.index_version}"
        )
    return 0


def report_failures(stage: str, failures: list[str]) -> None:
    """Never let a provider error pass silently.

    A rate-limited generator returns far fewer items than expected, and without
    this the run looks like it simply found less to say.
    """
    if not failures:
        return
    print(f"  {len(failures)} {stage} failures:", flush=True)
    for failure in failures[:5]:
        print(f"    {failure}", flush=True)
    if len(failures) > 5:
        print(f"    ... and {len(failures) - 5} more", flush=True)


def report_split(name: str, rows: list[dict[str, Any]]) -> None:
    languages = Counter(str(row["language"]) for row in rows)
    unanswerable = sum(not row["answerable"] for row in rows)
    share = unanswerable / len(rows) if rows else 0.0
    print(
        f"{name}: {len(rows)} items, {unanswerable} unanswerable ({share:.0%}), "
        f"languages {dict(languages)}"
    )


def check_minimums(
    golden: list[dict[str, Any]],
    calibration: list[dict[str, Any]],
    pairs: list[dict[str, Any]],
) -> None:
    """Fail here rather than three commands later, with the reason named.

    Each bound belongs to a downstream consumer: `load_golden` for the golden
    set, `calibrate.run` for the split and the pairs, and `choose_gate`'s
    false-answer constraint for the negative count - with fewer than 40 negatives
    a single false positive already exceeds 0.05 and calibration aborts.
    """
    problems: list[str] = []
    if len(golden) < 200:
        problems.append(f"golden has {len(golden)} items; load_golden requires 200")
    unanswerable = sum(not row["answerable"] for row in golden)
    if golden and unanswerable / len(golden) < 0.25:
        problems.append(f"golden is {unanswerable / len(golden):.0%} unanswerable; need 25%")
    if len(calibration) < 30:
        problems.append(f"calibration has {len(calibration)} items; calibrate requires 30")
    negatives = sum(not row["answerable"] for row in calibration)
    if negatives < 40:
        problems.append(
            f"calibration has {negatives} unanswerable items; choose_gate needs ~40 "
            "before it can tolerate a single false positive within its 0.05 budget"
        )
    if len(pairs) < 30:
        problems.append(f"{len(pairs)} cache pairs; calibrate requires 30")
    overlap = {row["id"] for row in golden} & {row["id"] for row in calibration}
    if overlap:
        problems.append(f"{len(overlap)} items appear in both splits")
    if problems:
        raise SystemExit("\n".join(f"  - {problem}" for problem in problems))


async def activate_only(index_version: str) -> int:
    """Flip the alias onto a collection that was built with --no-activate."""
    settings = Settings()
    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    manifest = await registry.manifest(index_version)
    if manifest is None:
        raise SystemExit(f"no index manifest named {index_version!r}")
    builder = build_index_builder(settings, registry)
    activated = await builder.activate(manifest)
    print(f"{activated.collection_name} is now serving as {settings.qdrant_alias}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strategies", nargs="*", default=None)
    parser.add_argument(
        "--golden-strategy",
        default=None,
        help="must be the first configured strategy; labels are strategy-specific",
    )
    parser.add_argument("--languages", default=",".join(DEFAULT_LANGUAGES))
    parser.add_argument("--refresh-translations", action="store_true")
    parser.add_argument(
        "--max-translation-sections",
        type=int,
        default=0,
        help="translate only this many prose sections per language (0 = all); "
        "sampled across the corpus, for runs bounded by a provider token quota",
    )
    parser.add_argument(
        "--site-url",
        default=None,
        help="base URL of the marketing site, so doc citations link to /docs/<slug>",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=200,
        help="cap English question-generation calls; sampled across the corpus, "
        "not truncated, so coverage stays even",
    )
    parser.add_argument("--per-topic", type=int, default=5)
    parser.add_argument("--cache-pair-samples", type=int, default=60)
    parser.add_argument("--max-chunks", type=int, default=120_000)
    parser.add_argument("--index-version", default=None)
    parser.add_argument("--golden-output", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument(
        "--calibration-output", type=Path, default=Path("eval/calibration.jsonl")
    )
    parser.add_argument(
        "--cache-pairs-output", type=Path, default=Path("eval/cache_pairs.jsonl")
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="build and validate without flipping the alias, so the new corpus can be "
        "calibrated against before it serves traffic",
    )
    parser.add_argument(
        "--activate",
        metavar="INDEX_VERSION",
        default=None,
        help="flip the alias onto a collection previously built with --no-activate",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.activate:
        raise SystemExit(asyncio.run(activate_only(args.activate)))
    raise SystemExit(asyncio.run(build(args)))


if __name__ == "__main__":
    main()
