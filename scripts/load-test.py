#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx


async def one_query(client: httpx.AsyncClient, url: str, token: str, query: str) -> float:
    started = time.perf_counter()
    headers = {"Authorization": f"Bearer {token}"}
    async with client.stream(
        "POST", f"{url.rstrip('/')}/v1/query/stream", headers=headers, json={"query": query}
    ) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if line.startswith("event: answer_chunk"):
                return time.perf_counter() - started
    raise RuntimeError("stream ended without an answer chunk")


async def run(args: argparse.Namespace) -> int:
    queries = [json.loads(line)["query"] for line in args.dataset.read_text().splitlines() if line]
    latencies: list[float] = []
    failures = 0
    interval = 1 / args.qps
    timeout = httpx.Timeout(30, connect=5)
    async with httpx.AsyncClient(timeout=timeout, verify=not args.insecure) as client:
        tasks: set[asyncio.Task[float]] = set()
        deadline = time.monotonic() + args.duration
        index = 0
        while time.monotonic() < deadline:
            tasks.add(
                asyncio.create_task(
                    one_query(client, args.url, args.token, queries[index % len(queries)])
                )
            )
            index += 1
            await asyncio.sleep(interval)
        for result in await asyncio.gather(*tasks, return_exceptions=True):
            if isinstance(result, BaseException):
                failures += 1
            else:
                latencies.append(result)
    if not latencies:
        raise RuntimeError("all load-test requests failed")
    p95 = statistics.quantiles(latencies, n=100, method="inclusive")[94]
    report = {"requests": len(latencies) + failures, "failures": failures, "ttft_p95": p95}
    print(json.dumps(report, indent=2))
    return 0 if p95 < 2 and failures / (len(latencies) + failures) <= 0.01 else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--qps", type=float, default=20)
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--insecure", action="store_true")
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
