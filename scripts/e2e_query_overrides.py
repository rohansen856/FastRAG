#!/usr/bin/env python3
"""Smoke-test query overrides end-to-end (API + optional website proxy)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

TOKEN = os.environ.get("FASTRAG_QUERY_TOKEN", "fastrag-query-Hy3nQvJ2xLpR8mTcWk6bZs")
API = os.environ.get("FASTRAG_API_URL", "http://localhost:8001")
WEB = os.environ.get("FASTRAG_WEB_URL", "http://localhost:3000")
QUESTION = "what is a corporation"


def post_stream(url: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode()
    for block in raw.replace("\r\n", "\n").split("\n\n"):
        event = "message"
        data_lines: list[str] = []
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].strip())
        if event == "final" and data_lines:
            return json.loads("\n".join(data_lines))
    raise RuntimeError(f"no final event in response from {url}")


def assert_close(actual: float | None, expected: float, label: str) -> None:
    if actual is None:
        raise AssertionError(f"{label}: expected {expected}, got null")
    if abs(actual - expected) > 0.001:
        raise AssertionError(f"{label}: expected {expected}, got {actual}")


def check_trace(trace: dict, overrides: dict, *, expect_crag_skipped: bool) -> None:
    applied = trace.get("overrides_applied") or {}
    for key in ("skip_cache", "crag_enabled", "candidate_k", "context_top_k"):
        if key in overrides:
            if applied.get(key) != overrides[key]:
                raise AssertionError(
                    f"overrides_applied.{key}: {applied.get(key)!r} != {overrides[key]!r}"
                )

    if "reranker_threshold" in overrides:
        assert_close(
            trace.get("reranker_threshold"),
            overrides["reranker_threshold"],
            "trace.reranker_threshold",
        )
    if "crag_confident_threshold" in overrides:
        assert_close(
            trace.get("crag_confident_threshold"),
            overrides["crag_confident_threshold"],
            "trace.crag_confident_threshold",
        )
    if "offtopic_threshold" in overrides:
        assert_close(
            trace.get("offtopic_threshold"),
            overrides["offtopic_threshold"],
            "trace.offtopic_threshold",
        )

    if overrides.get("skip_cache"):
        for stage_id in ("exact_cache", "semantic_cache"):
            stage = next(s for s in trace["stages"] if s["id"] == stage_id)
            if stage["status"] != "skipped":
                raise AssertionError(f"{stage_id} should be skipped, got {stage['status']}")

    crag = next(s for s in trace["stages"] if s["id"] == "crag")
    if expect_crag_skipped and crag["status"] != "skipped":
        raise AssertionError(f"CRAG should be skipped, got {crag['status']}")
    skipped_unexpectedly = (
        not expect_crag_skipped
        and crag["status"] == "skipped"
        and overrides.get("crag_enabled") is not False
    )
    if skipped_unexpectedly:
        raise AssertionError("CRAG unexpectedly skipped")

    if "candidate_k" in overrides:
        if len(trace.get("retrieved") or []) > overrides["candidate_k"]:
            raise AssertionError(
                f"retrieved {len(trace['retrieved'])} > candidate_k {overrides['candidate_k']}"
            )
    if "context_top_k" in overrides:
        if len(trace.get("contexts") or []) > overrides["context_top_k"]:
            raise AssertionError(
                f"contexts {len(trace['contexts'])} > context_top_k {overrides['context_top_k']}"
            )

    llm = overrides.get("llm") or {}
    if llm.get("model"):
        if trace.get("generator_model") != llm["model"]:
            raise AssertionError(
                f"generator_model {trace.get('generator_model')!r} != {llm['model']!r}"
            )


def run_case(
    name: str, url: str, payload: dict, overrides: dict, *, expect_crag_skipped: bool
) -> None:
    print(f"\n=== {name} ===")
    response = post_stream(url, payload)
    trace = response.get("trace")
    if not trace:
        raise AssertionError("missing trace")
    check_trace(trace, overrides, expect_crag_skipped=expect_crag_skipped)
    print(f"  outcome={response.get('outcome')} cache={response.get('cache_status')}")
    print(f"  overrides_applied={json.dumps(trace.get('overrides_applied'))}")
    print("  OK")


def main() -> int:
    baseline = post_stream(
        f"{API}/v1/query/stream",
        {"query": QUESTION, "strategy": "sentence"},
    )
    base_trace = baseline["trace"]
    print(
        "Baseline trace thresholds:",
        base_trace.get("reranker_threshold"),
        base_trace.get("offtopic_threshold"),
    )

    custom_overrides = {
        "skip_cache": True,
        "crag_enabled": False,
        "candidate_k": 12,
        "context_top_k": 2,
        "reranker_threshold": 0.25,
        "crag_confident_threshold": 0.55,
        "offtopic_threshold": -0.45,
        "llm": {"max_tokens": 180, "model": base_trace.get("generator_model")},
    }

    api_payload = {
        "query": QUESTION,
        "strategy": "metadata_aware",
        "language": "en-IN",
        "overrides": custom_overrides,
    }
    run_case(
        "API all overrides",
        f"{API}/v1/query/stream",
        api_payload,
        custom_overrides,
        expect_crag_skipped=True,
    )

    # Website proxy (same token, server-side)
    try:
        run_case(
            "Website proxy all overrides",
            f"{WEB}/api/rag/v1/query/stream",
            api_payload,
            custom_overrides,
            expect_crag_skipped=True,
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        print(f"\nWebsite proxy failed ({exc.code}): {body[:300]}", file=sys.stderr)
        print(
            "  (Ensure website dev server uses FASTRAG_API_URL=http://localhost:8001)",
            file=sys.stderr,
        )
        return 1

    # No-change re-run: empty overrides object should not 422
    noop = post_stream(
        f"{API}/v1/query/stream",
        {"query": QUESTION, "strategy": "sentence"},
    )
    if noop.get("trace", {}).get("overrides_applied"):
        print("WARN: baseline query returned overrides_applied unexpectedly")
    else:
        print("\n=== No overrides baseline ===\n  OK")

    print("\nAll override e2e checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
