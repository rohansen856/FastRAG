#!/usr/bin/env python
"""Build the multilingual corpus and golden set from ai4bharat/MSMARCO-XI.

The full dataset is 11.45M rows / 55.6 GB, so it is streamed and subset rather
than downloaded. Two constraints shape the defaults:

* Qdrant's free tier holds roughly 1 GB. Every chunking strategy is indexed side
  by side in one collection so they can be compared at query time, which
  multiplies the vector count by the number of strategies. `--max-chunks` is the
  hard cap that keeps the result inside the free tier.
* Every shard upstream is written as a single parquet row group, so a reader has
  to decompress the whole group no matter how few rows it wants. The train shards
  are 3.7 GB each and expand to roughly 10 GB in memory, which is why this reads
  the validation shards instead: same schema, 97,941 rows, ~470 MB each, and a
  ~1.2 GB working set. Telugu is only published for validation anyway, so using
  it for every language also keeps the split consistent across languages.

The golden set is derived from the dataset's own labels: `is_selected` marks the
relevant passage, and MS MARCO's "No Answer Present." marker supplies the
genuinely unanswerable queries the abstention gate is calibrated against.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastrag.chunking import SourceDocument, build_strategy, chunk_document  # noqa: E402
from fastrag.config import Settings  # noqa: E402
from fastrag.jobs import build_index_builder  # noqa: E402
from fastrag.registry import PostgresIndexRegistry  # noqa: E402

REPO = "ai4bharat/MSMARCO-XI"

# Upstream uses three-letter file prefixes for the shard names.
LANGUAGES: dict[str, str] = {
    "hi": "hin",
    "bn": "ben",
    "ta": "tam",
    "mr": "mar",
    "te": "tel",
}

COLUMNS = ["query", "Answer", "query_id", "query_type", "passages", "Eng_Query", "Eng_Answer"]

NO_ANSWER_MARKERS = {"no answer present.", "no answer present", ""}


def stream_rows(prefix: str, limit: int, *, batch_size: int = 256) -> list[dict[str, Any]]:
    """Read the first `limit` rows, projecting only the columns we use."""
    import pyarrow.parquet as pq
    from huggingface_hub import HfFileSystem

    path = f"datasets/{REPO}/validation/{prefix}val.parquet"
    handle = HfFileSystem().open(path, "rb")
    reader = pq.ParquetFile(handle)
    rows: list[dict[str, Any]] = []
    for batch in reader.iter_batches(batch_size=batch_size, columns=COLUMNS):
        rows.extend(batch.to_pylist())
        if len(rows) >= limit:
            break
    return rows[:limit]


def document_id(language: str, query_id: Any, index: int) -> str:
    raw = f"{language}:{query_id}:{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def extract(
    row: dict[str, Any], language: str, *, english: bool
) -> tuple[list[SourceDocument], str, str | None, list[str]]:
    """Turn one MS MARCO row into documents plus its golden labels.

    Returns the documents, the query, the reference answer (None when the row is
    labelled unanswerable) and the document IDs of the passages marked relevant.
    """
    passages = row.get("passages") or {}
    key = "English_passages" if english else "Translated_passages"
    texts = passages.get(key) or []
    selected = passages.get("is_selected") or []
    query = str(row["Eng_Query"] if english else row["query"]).strip()
    answer_raw = str(row["Eng_Answer"] if english else row["Answer"] or "").strip()
    answer = None if answer_raw.casefold() in NO_ANSWER_MARKERS else answer_raw

    documents: list[SourceDocument] = []
    relevant: list[str] = []
    tag = "en" if english else language
    for index, text in enumerate(texts):
        text = str(text).strip()
        if not text:
            continue
        identifier = document_id(tag, row.get("query_id"), index)
        documents.append(
            SourceDocument(
                document_id=identifier,
                text=text,
                title=f"MS MARCO {tag} passage {row.get('query_id')}#{index}",
                source_uri=f"msmarco-xi://{tag}/{row.get('query_id')}/{index}",
                language=tag,
                metadata={
                    "query": query,
                    "category": str(row.get("query_type") or "unknown"),
                    "language": tag,
                },
            )
        )
        if index < len(selected) and int(selected[index]) == 1:
            relevant.append(identifier)
    return documents, query, answer, relevant


async def build(args: argparse.Namespace) -> int:
    settings = Settings()
    strategy_names = args.strategies or settings.chunk_strategy_list or ["sentence"]
    golden_strategy = args.golden_strategy or strategy_names[0]
    if golden_strategy not in strategy_names:
        raise SystemExit(f"--golden-strategy {golden_strategy} is not in {strategy_names}")

    from fastrag.bootstrap import build_embedder_and_reranker

    embedder, _ = build_embedder_and_reranker(settings)
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
    golden: list[dict[str, Any]] = []
    # document id -> chunk ids, for the strategy the golden set is scored against
    chunk_index: dict[str, list[str]] = defaultdict(list)
    digest = hashlib.sha256()
    seen_chunk_ids: set[str] = set()

    targets = list(LANGUAGES.items())
    if args.include_english:
        # English passages ride along in every shard, so this costs no extra download.
        targets.append(("en", "hin"))

    for language, prefix in targets:
        english = language == "en"
        print(f"streaming {language} from {prefix}val.parquet...", flush=True)
        rows = stream_rows(prefix, args.rows_per_language)
        for row in rows:
            if len(chunks) >= args.max_chunks:
                break
            documents, query, answer, relevant = extract(row, language, english=english)
            if not documents or not query:
                continue
            for document in documents:
                digest.update(document.document_id.encode())
                digest.update(document.text.encode())
                for payload in await chunk_document(document, strategies):
                    if payload["chunk_id"] in seen_chunk_ids:
                        continue
                    seen_chunk_ids.add(payload["chunk_id"])
                    chunks.append(payload)
                    if payload["strategy"] == golden_strategy:
                        chunk_index[document.document_id].append(payload["chunk_id"])
            relevant_chunks = [
                chunk_id for document_key in relevant for chunk_id in chunk_index[document_key]
            ]
            answerable = answer is not None and bool(relevant_chunks)
            golden.append(
                {
                    "id": f"{language}-{row.get('query_id')}",
                    "query": query,
                    "reference_answer": answer if answerable else None,
                    "answerable": answerable,
                    "relevant_chunk_ids": relevant_chunks if answerable else [],
                    "reference_contexts": [],
                    "category": str(row.get("query_type") or "unknown"),
                    "language": language,
                }
            )
        print(f"  {len(chunks)} chunks, {len(golden)} golden items", flush=True)
        if len(chunks) >= args.max_chunks:
            print("reached --max-chunks; stopping", flush=True)
            break

    golden = balance_golden(golden, minimum=args.min_golden)
    args.golden_output.parent.mkdir(parents=True, exist_ok=True)
    args.golden_output.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in golden) + "\n"
    )
    print(f"wrote {len(golden)} golden items to {args.golden_output}")

    if args.dry_run:
        print(json.dumps({"chunks": len(chunks), "golden": len(golden)}, indent=2))
        return 0

    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    builder = build_index_builder(settings, registry)
    manifest = await builder.build_from_chunks(
        chunks, content_version=digest.hexdigest(), version=args.index_version
    )
    print(
        json.dumps(
            {
                "index_version": manifest.index_version,
                "collection": manifest.collection_name,
                "chunks": manifest.chunk_count,
                "strategies": list(manifest.chunk_strategies),
                "languages": list(manifest.languages),
            },
            indent=2,
        )
    )
    return 0


def balance_golden(
    items: list[dict[str, Any]], *, minimum: int, unanswerable_ratio: float = 0.35
) -> list[dict[str, Any]]:
    """Hold the unanswerable share near a target ratio.

    MS MARCO's validation split is majority "No Answer Present.", so taking the
    rows as they come would leave recall and MRR measured on a small answerable
    minority. The gate needs at least 25% unanswerable; this aims a little above
    that and keeps the languages evenly represented within each group.
    """
    answerable = [item for item in items if item["answerable"]]
    unanswerable = [item for item in items if not item["answerable"]]
    if not unanswerable:
        raise SystemExit("no unanswerable rows found; cannot satisfy the golden-set gate")
    if not answerable:
        raise SystemExit("no answerable rows found; check the passage labels")

    total = max(minimum, min(len(answerable) + len(unanswerable), minimum * 2))
    want_unanswerable = min(len(unanswerable), max(1, round(total * unanswerable_ratio)))
    want_answerable = min(len(answerable), total - want_unanswerable)
    # If one side is short, spend the remaining budget on the other.
    want_unanswerable = min(len(unanswerable), total - want_answerable)

    combined = _round_robin(answerable, want_answerable) + _round_robin(
        unanswerable, want_unanswerable
    )
    if len(combined) < minimum:
        raise SystemExit(
            f"only {len(combined)} golden items available; need {minimum}. "
            "Raise --rows-per-language."
        )
    combined.sort(key=lambda item: item["id"])
    return combined


def _round_robin(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Take `count` items spread evenly across languages."""
    by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        by_language[str(item["language"])].append(item)
    selected: list[dict[str, Any]] = []
    index = 0
    while len(selected) < count:
        added = False
        for bucket in by_language.values():
            if index < len(bucket) and len(selected) < count:
                selected.append(bucket[index])
                added = True
        if not added:
            break
        index += 1
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    # ~74 chunks per row across six strategies, so 250 rows x 6 targets lands
    # near 110K chunks, just inside the --max-chunks cap.
    parser.add_argument("--rows-per-language", type=int, default=250)
    parser.add_argument(
        "--max-chunks",
        type=int,
        default=120_000,
        help="hard cap sized for the Qdrant free tier across all strategies",
    )
    parser.add_argument("--strategies", nargs="*", default=None)
    parser.add_argument("--golden-strategy", default=None)
    parser.add_argument("--golden-output", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--min-golden", type=int, default=200)
    parser.add_argument("--index-version", default=None)
    parser.add_argument("--include-english", action="store_true", default=True)
    parser.add_argument("--no-english", dest="include_english", action="store_false")
    parser.add_argument(
        "--dry-run", action="store_true", help="build chunks and golden set without indexing"
    )
    raise SystemExit(asyncio.run(build(parser.parse_args())))


if __name__ == "__main__":
    main()
