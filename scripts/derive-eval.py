#!/usr/bin/env python
"""Build the evaluation sets from corpus structure, without any generator calls.

`scripts/ingest-self.py` writes better questions, but it needs a generator quota
that a free tier does not always have - and a freshly indexed corpus cannot be
served at all until some calibration exists, because every threshold in
`config/calibration.json` is fitted against one corpus and startup now checks
which. This produces a usable set from what the repository already states about
itself, so an index can be calibrated and activated the same day it is built.

Read the numbers accordingly: a heading-derived question shares vocabulary with
the chunk it points at, so the thresholds it produces are optimistic. Replace
them with `ingest-self.py` output when quota allows.

Runs against an existing collection. Chunk ids are recomputed locally - they are
a hash of the text, not of anything the index holds - so nothing is re-embedded
or re-uploaded.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from selfcorpus import derive, sources  # noqa: E402
from selfcorpus import golden as golden_mod  # noqa: E402
from selfcorpus.evalsets import (  # noqa: E402
    assert_labels_in_collection,
    assert_labels_indexed,
    check_minimums,
    report_split,
    write_jsonl,
)

from fastrag.chunking import build_strategy, chunk_document  # noqa: E402
from fastrag.config import Settings  # noqa: E402


async def main(args: argparse.Namespace) -> int:
    settings = Settings()
    root = sources.repo_root()
    commit = sources.git_commit(root)

    strategy_names = args.strategies or settings.chunk_strategy_list or ["sentence"]
    golden_strategy = strategy_names[0]
    if golden_strategy in {"semantic", "metadata_aware"}:
        raise SystemExit(f"{golden_strategy!r} produces unstable chunk ids; use 'sentence'")

    documents = sources.build_documents(sources.load_repo_files(root), commit)
    strategies = [
        build_strategy(
            name, chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap
        )
        for name in strategy_names
        if name != "semantic"  # the only strategy that needs an embedder
    ]
    chunks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for document in documents:
        for payload in await chunk_document(document, strategies):
            if payload["chunk_id"] in seen:
                continue
            seen.add(payload["chunk_id"])
            chunks.append(payload)
    print(f"{len(documents)} documents -> {len(chunks)} chunks", flush=True)

    key_by_id = {d.document_id: str(d.metadata["document_key"]) for d in documents}
    chunk_index = golden_mod.chunk_ids_by_document(
        chunks, golden_strategy, key_by_id, language="en"
    )
    answerable = derive.derive_answerable(documents, chunk_index, limit=args.max_questions)
    unanswerable = derive.derive_unanswerable(per_topic=args.per_topic)
    print(f"derived {len(answerable)} answerable, {len(unanswerable)} unanswerable", flush=True)

    from fastrag.bootstrap import build_embedder_and_reranker, build_retriever

    embedder, reranker = build_embedder_and_reranker(settings)
    retriever = build_retriever(settings)
    collection = args.collection or None

    async def retrieve(query: str, vector: list[float], limit: int) -> Any:
        return await retriever.retrieve(
            query, vector, limit, collection=collection, strategy=golden_strategy
        )

    # Where the answerable population sits, so "scores like an answer" is
    # measured against this corpus rather than guessed.
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

    pool = sorted({c.id: c for c in (answerable + kept)}.values(), key=lambda c: c.id)
    golden, calibration = golden_mod.split_pool(pool)
    golden_rows = [c.as_record() for c in golden]
    calibration_rows = [c.as_record() for c in calibration]

    assert_labels_indexed(golden_rows, chunks)
    assert_labels_indexed(calibration_rows, chunks)
    if collection:
        from fastrag.adapters.retrieval import connect_qdrant

        client = connect_qdrant(
            settings.qdrant_url,
            settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        )
        assert_labels_in_collection(golden_rows, client, collection)
        assert_labels_in_collection(calibration_rows, client, collection)
    report_split("golden", golden_rows)
    report_split("calibration", calibration_rows)

    pairs = golden_mod.cache_pairs(calibration, derive_paraphrases(calibration))
    check_minimums(golden_rows, calibration_rows, pairs)

    write_jsonl(args.golden_output, golden_rows)
    write_jsonl(args.calibration_output, calibration_rows)
    write_jsonl(args.cache_pairs_output, pairs)
    print(
        f"wrote {len(golden_rows)} golden, {len(calibration_rows)} calibration, "
        f"{len(pairs)} cache pairs"
    )
    return 0


def derive_paraphrases(candidates: list[Any]) -> dict[str, str]:
    """Restate each question without a generator.

    The point of a cache positive is two spellings of one intent, so these drop
    the framing and keep the subject - closer than a template swap, and far less
    trivially similar than the shipped `"Please answer: " + query` pairs.
    """
    out: dict[str, str] = {}
    for candidate in candidates:
        query = candidate.query
        for prefix in ("In FastRAG's ", "What does ", "How does FastRAG handle ", "What is "):
            if query.startswith(prefix):
                stripped = query[len(prefix):].rstrip("?").strip()
                out[candidate.id] = f"explain {stripped}"
                break
    return out


def cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", default=None, help="read this collection, not the alias")
    parser.add_argument("--strategies", nargs="*", default=None)
    parser.add_argument("--max-questions", type=int, default=260)
    parser.add_argument("--per-topic", type=int, default=5)
    parser.add_argument("--golden-output", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--calibration-output", type=Path, default=Path("eval/calibration.jsonl"))
    parser.add_argument("--cache-pairs-output", type=Path, default=Path("eval/cache_pairs.jsonl"))
    raise SystemExit(asyncio.run(main(parser.parse_args())))


if __name__ == "__main__":
    cli()
