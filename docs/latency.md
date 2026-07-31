# Latency

The target is **under 200ms for the retrieval pipeline**: guardrails, embedding, cache
lookup, retrieval, reranking, and CRAG. Speech-to-text and token generation are measured and
reported, but separately, and they are not counted toward that number.

That split needs justifying rather than assuming, so here it is. Token generation is bounded
by how fast the model emits tokens, and no retrieval work changes it; a 70B model producing
150 tokens cannot do so in 200ms on any tier. Speech-to-text is a network round trip to
Sarvam. Both are real user-facing latency and both are reported at every percentile — but
folding them into one blended number would mean an improvement in retrieval could be erased
by a slower model, and nobody could tell which had happened. Every stage is reported at every
percentile precisely so a regression can be attributed.

## Running it

```bash
FASTRAG_PROFILE=local uv run python scripts/bench-latency.py \
  --url https://localhost --token "$FASTRAG_QUERY_API_KEY" --label local --insecure

FASTRAG_PROFILE=cloud uv run python scripts/bench-latency.py \
  --url https://your-api.onrender.com --token "$FASTRAG_QUERY_API_KEY" --label cloud
```

Both runs merge into `bench/results/summary.json`, which the UI's benchmark dashboard reads
and `GET /v1/bench` serves. `--require-target` exits non-zero when the retrieval pipeline
misses 200ms at P95, which is what CI should gate on.

The first few requests pay model load and TLS setup, so `--warmup 3` excludes them by
default. On a 200-sample run a single cold start would otherwise be P100 outright and the
number would describe process startup rather than query latency.

## Reading the report

P50, P70, P95, P100 per stage, plus `retrieval_pipeline_ms` totalling the six stages the
target covers, plus `ttft_ms` for time to first validated answer sentence — which is the
number a user actually experiences, since the answer starts appearing then.

P100 is the slowest single request in the sample. It is worth reporting because it exposes
the worst case, but it is one observation: it is not stable across runs and should not be
treated as an SLO. P95 is what an SLO gets set on.

`meets_200ms_p50` and `meets_200ms_p95` are computed against the retrieval pipeline total.

## Where the time goes

**Local profile.** Everything is in-process or on localhost. Embedding is an ONNX forward
pass on a short query; reranking is a cross-encoder over 20 candidates and is normally the
largest single stage; Qdrant hybrid retrieval over a local collection is a few milliseconds.
Guardrails are a regex sweep and a dot product. This is where the sub-200ms claim is
measured and where it holds.

**Cloud profile.** Embedding and reranking each become an HTTPS round trip to Jina, and
retrieval becomes a round trip to Qdrant Cloud. Three network hops on the retrieval path
mean 200ms is not achievable, and the report will say so honestly rather than quietly
excluding the network. Render's free tier also spins down after 15 minutes of inactivity, so
the first request after idle pays a cold start of several seconds; that is an availability
characteristic of the tier, not a pipeline property, which is what `--warmup` separates out.

## Keeping the budget

- `FASTRAG_REQUEST_DEADLINE_SECONDS` is a wall-clock budget shared by every stage. A slow
  stage is cut off rather than allowed to consume the whole request, and a retry whose
  backoff would exceed the remaining budget is abandoned rather than started.
- The exact cache short-circuits everything downstream, so cache hits are effectively free.
  Benchmark numbers are dominated by whatever your hit rate is; the report breaks out
  outcomes by cache status so a suspiciously good result can be checked.
- CRAG adds `crag_ms`, near zero when retrieval grades `CORRECT` and visible only in the
  tail. `FASTRAG_CRAG_ENABLED=false` gives the correction-free baseline.
- Reranking is the biggest lever in the local profile. `FASTRAG_RETRIEVAL_CANDIDATE_K`
  trades recall for rerank time roughly linearly.

## Load testing

`scripts/load-test.py` covers sustained throughput and concurrency; `bench-latency.py`
covers per-stage attribution. They answer different questions and both belong in a release.
See [benchmarking.md](benchmarking.md).
