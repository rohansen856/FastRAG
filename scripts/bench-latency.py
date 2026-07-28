#!/usr/bin/env python3
"""Latency benchmark reporting P50 / P70 / P100 with a per-stage breakdown.

The 200ms target applies to the retrieval pipeline: guardrails, embedding, cache,
retrieval, reranking and CRAG. Speech-to-text and token generation are reported
separately because both are provider-bound and neither is part of the retrieval
path the target describes. Reporting one blended number would hide which stage
actually moved when something regresses, so every stage is reported at each
percentile.

Run once per profile and the two reports can be compared directly:

    FASTRAG_PROFILE=local uv run python scripts/bench-latency.py --url ... --label local
    FASTRAG_PROFILE=cloud uv run python scripts/bench-latency.py --url ... --label cloud
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path
from typing import Any

import httpx

STAGES = (
    "stt_ms",
    "guardrail_ms",
    "embedding_ms",
    "cache_ms",
    "retrieval_ms",
    "rerank_ms",
    "crag_ms",
    "generation_ms",
    "total_ms",
)

RETRIEVAL_STAGES = (
    "guardrail_ms",
    "embedding_ms",
    "cache_ms",
    "retrieval_ms",
    "rerank_ms",
    "crag_ms",
)

TARGET_MS = 200.0


def percentiles(values: list[float]) -> dict[str, float]:
    """P50/P70/P100 plus P95, which is what an SLO would actually be set on."""
    if not values:
        return {}
    ordered = sorted(values)

    def pick(fraction: float) -> float:
        index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
        return round(ordered[index], 2)

    return {
        "p50": pick(0.50),
        "p70": pick(0.70),
        "p95": pick(0.95),
        "p100": round(ordered[-1], 2),
        "mean": round(statistics.fmean(ordered), 2),
        "count": len(ordered),
    }


async def one_query(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    query: str,
    strategy: str | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    ttft: float | None = None
    payload: dict[str, Any] = {"query": query}
    if strategy:
        payload["strategy"] = strategy
    async with client.stream(
        "POST",
        f"{url.rstrip('/')}/v1/query/stream",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    ) as response:
        response.raise_for_status()
        event = ""
        async for line in response.aiter_lines():
            if line.startswith("event: "):
                event = line[7:].strip()
            elif line.startswith("data: "):
                if event == "answer_chunk" and ttft is None:
                    ttft = (time.perf_counter() - started) * 1000
                elif event == "final":
                    final = json.loads(line[6:])
                    return {
                        "timings": final["timings"],
                        "outcome": final["outcome"],
                        "cache_status": final["cache_status"],
                        "crag": (final.get("crag") or {}).get("action"),
                        "ttft_ms": ttft,
                        "wall_ms": (time.perf_counter() - started) * 1000,
                    }
                elif event == "error":
                    raise RuntimeError(line[6:])
    raise RuntimeError("stream ended without a final event")


async def run(args: argparse.Namespace) -> int:
    queries = [json.loads(line)["query"] for line in args.dataset.read_text().splitlines() if line]
    if not queries:
        raise SystemExit("dataset contained no queries")
    queries = queries[: args.samples]

    results: list[dict[str, Any]] = []
    failures: list[str] = []
    semaphore = asyncio.Semaphore(args.concurrency)
    timeout = httpx.Timeout(60, connect=10)

    async def worker(query: str) -> None:
        async with semaphore:
            try:
                results.append(await one_query(client, args.url, args.token, query, args.strategy))
            except Exception as exc:  # noqa: BLE001 - recorded, not raised
                failures.append(f"{type(exc).__name__}: {exc}")

    async with httpx.AsyncClient(timeout=timeout, verify=not args.insecure) as client:
        if args.warmup:
            # The first request pays model load and TLS setup; excluding it stops
            # a cold start from dominating P100 on a small sample.
            for query in queries[: args.warmup]:
                try:
                    await one_query(client, args.url, args.token, query, args.strategy)
                except Exception:  # noqa: BLE001, S110 - warmup failures are not results
                    pass
        await asyncio.gather(*(worker(query) for query in queries))

    if not results:
        print(json.dumps({"failures": failures[:5]}, indent=2))
        raise SystemExit("every benchmark request failed")

    stages = {
        stage: percentiles([float(item["timings"][stage]) for item in results]) for stage in STAGES
    }
    retrieval_totals = [
        sum(float(item["timings"][stage]) for stage in RETRIEVAL_STAGES) for item in results
    ]
    ttfts = [item["ttft_ms"] for item in results if item["ttft_ms"] is not None]

    retrieval = percentiles(retrieval_totals)
    report = {
        "label": args.label,
        "url": args.url,
        "strategy": args.strategy,
        "samples": len(results),
        "failures": len(failures),
        "failure_examples": failures[:3],
        "retrieval_pipeline_ms": retrieval,
        "meets_200ms_p50": retrieval.get("p50", float("inf")) < TARGET_MS,
        "meets_200ms_p95": retrieval.get("p95", float("inf")) < TARGET_MS,
        "ttft_ms": percentiles(ttfts),
        "stages": stages,
        "outcomes": _counts(item["outcome"] for item in results),
        "cache": _counts(item["cache_status"] for item in results),
        "crag": _counts(item["crag"] or "none" for item in results),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    _merge_summary(args.output, args.label, report)
    print(json.dumps(report, indent=2))
    if args.require_target and not report["meets_200ms_p95"]:
        return 1
    return 0


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def _merge_summary(path: Path, label: str, report: dict[str, Any]) -> None:
    """Keep both profile runs in one file so the UI can chart them together."""
    summary: dict[str, Any] = {}
    if path.is_file():
        try:
            summary = json.loads(path.read_text())
        except json.JSONDecodeError:
            summary = {}
    summary[label] = report
    summary["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    path.write_text(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--dataset", type=Path, default=Path("eval/golden.jsonl"))
    parser.add_argument("--label", default="local", help="profile name this run represents")
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--strategy", default=None)
    parser.add_argument("--output", type=Path, default=Path("bench/results/summary.json"))
    parser.add_argument("--insecure", action="store_true")
    parser.add_argument(
        "--require-target",
        action="store_true",
        help="exit non-zero when the retrieval pipeline misses 200ms at P95",
    )
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
