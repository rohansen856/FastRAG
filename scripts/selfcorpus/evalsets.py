"""Assemble and validate the evaluation sets, however the questions were produced.

Shared by the generator-written path (`scripts/ingest-self.py`) and the derived
one (`scripts/derive-eval.py`), so the bounds each downstream consumer requires
are enforced identically either way.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def assert_labels_indexed(rows: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> None:
    """Every label must name a chunk that is actually in the collection.

    `scripts/check-golden.py` cannot do this - it validates the schema and has no
    chunk set. Without it a silent chunking change turns recall@20 to zero and
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
    languages = Counter(str(row.get("language", "en")) for row in rows)
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


def assert_labels_in_collection(
    rows: list[dict[str, Any]], client: Any, collection: str
) -> None:
    """Verify labels against the collection that will actually serve them.

    `assert_labels_indexed` compares against chunks recomputed in this process,
    which catches a chunker change but not a corpus drift: edit a file between
    indexing and deriving and the recomputed ids agree with each other while
    disagreeing with the index. Retrieval then cannot find the labelled chunk and
    recall reads as a retrieval regression rather than a stale label.
    """
    wanted = sorted({cid for row in rows for cid in row["relevant_chunk_ids"]})
    if not wanted:
        return
    found: set[str] = set()
    for start in range(0, len(wanted), 256):
        batch = wanted[start : start + 256]
        points = client.retrieve(
            collection_name=collection, ids=batch, with_payload=False, with_vectors=False
        )
        found.update(str(point.id) for point in points)
    missing = [cid for cid in wanted if cid not in found]
    if missing:
        raise SystemExit(
            f"{len(missing)} of {len(wanted)} labelled chunks are absent from "
            f"{collection} (e.g. {missing[:3]}); the corpus changed after it was "
            "indexed - re-index before deriving labels against it"
        )
