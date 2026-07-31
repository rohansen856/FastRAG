# Benchmarking and evaluation

FastRAG has three separate gates: quality evaluation, latency/capacity testing, and the
per-stage latency benchmark. Passing one does not imply passing the others.

## Quality gate

Create `eval/golden.jsonl` with at least 200 reviewed records. At least 25 percent should be
unanswerable. Keep calibration data separate from regression data.

`scripts/ingest-msmarco.py` derives a golden set from the dataset's own labels: `is_selected`
marks the relevant passage and MS MARCO's "No Answer Present." marker supplies genuinely
unanswerable queries, targeting roughly 35 percent unanswerable. These are real labels rather
than fabricated ones, but they are the dataset's judgements, not yours — review them before
treating a release as gated.

Check dataset shape:

```bash
uv run python scripts/check-golden.py
```

Run the full evaluation against a running service:

```bash
uv run python -m fastrag.evaluation \
  --dataset eval/golden.jsonl \
  --api-url http://localhost \
  --output eval/results/report.json
```

Release thresholds:

- Recall@20 >= 0.95
- reranked MRR@5 >= 0.85
- faithfulness >= 0.90
- answer relevancy >= 0.90
- correctness >= 0.90
- false-answer rate <= 0.05
- citation validity = 1.0

RAGAS judge configuration should be pinned the same way as production providers. Do not compare
reports generated with different judge models as if they are the same measurement.

## Calibration gate

Generate the no-answer, semantic-cache, CRAG, and off-topic thresholds from held-out data:

```bash
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl \
  --cache-pairs eval/cache_pairs.jsonl
```

This produces four calibrated values, not one:

- `reranker_threshold` — the abstention gate, and CRAG's lower band.
- `crag_confident_threshold` — CRAG's upper band; above it, generate without correction.
- `cache_distance_threshold` — semantic cache cosine distance.
- `offtopic_threshold` — with the corpus centroid, the off-topic guardrail.

Recalibrate when you change dense embeddings, reranker, chunking, prompt, provider model,
profile, or corpus shape. Switching profile changes the embedding and reranking providers,
so thresholds from one profile are meaningless on the other. Do not loosen thresholds to make
a release pass without adding hard negatives and reviewing the error cases.

## Load test

Use the streaming endpoint because the service SLO is p95 time to first validated answer
sentence:

```bash
uv run python scripts/load-test.py \
  --url http://localhost \
  --token "$FASTRAG_QUERY_API_KEY" \
  --dataset eval/golden.jsonl \
  --qps 20 \
  --duration 300
```

The command exits nonzero if TTFT p95 is above two seconds or failure rate is above one
percent. Run it against both cold-cache and warm-cache traffic:

- cold cache: start after a cache namespace change or targeted cache cleanup;
- warm cache: replay a representative query mix after the service has been exercised.

## Per-stage latency benchmark

The load test answers "does it hold up under traffic". It does not tell you which stage got
slower. `scripts/bench-latency.py` reports P50/P70/P95/P100 for every stage plus the
retrieval-pipeline total that the sub-200ms target applies to:

```bash
FASTRAG_PROFILE=local uv run python scripts/bench-latency.py \
  --url http://localhost --token "$FASTRAG_QUERY_API_KEY" --label local --require-target
```

Run it once per profile; both results merge into `bench/results/summary.json`, which the UI
dashboard and `GET /v1/bench` read. Full detail in [latency.md](latency.md).

## What to record

Every benchmark report should include:

- git or image release;
- `FASTRAG_PROFILE` and the active embedding, reranking, and STT providers;
- active content version and Qdrant collection;
- dense model fingerprint and reranker fingerprint;
- provider base URL class and model name, plus any fallback that engaged;
- chunking strategies indexed and the strategy queried;
- whether CRAG and guardrails were enabled;
- prompt version and answer token limit;
- hardware profile;
- corpus size and chunk count;
- QPS, duration, concurrency shape, cache hit ratio;
- p50/p70/p95/p100 stage latencies, TTFT, failure rate;
- golden quality metrics and citation failure count.

`GET /build` reports the profile and active providers directly, which is the fastest way to
confirm what a benchmark actually measured.

## Interpreting failures

- Low Recall@20: ingestion, chunking, dense/BM25 retrieval, or embedding mismatch.
- Good Recall@20 but low MRR@5: reranker quality, candidate count, or threshold calibration.
- Good retrieval but low faithfulness: prompt/provider behavior or context budget.
- Citation failures: provider did not obey marker format or answer used unsupported claims.
- High TTFT with cache misses: provider generation or reranker latency.
- High TTFT with cache hits: Redis/network issues or response validation overhead.
- Cost spike: cache hit ratio drop, answer length growth, provider price change, or trace volume.
- Rising `crag_actions{action="incorrect"}`: the corpus no longer covers what is being asked.
- Rising `guardrail_blocks{rule="off_topic"}`: same signal from the input side, or a stale
  corpus centroid after a re-index.
- Rising `fastrag_retries` or `fastrag_circuit_trips`: a provider is rate-limiting you. On
  Groq's free tier this is 30 requests/minute and load tests will hit it.
- `generator_provider` not matching the configured primary: the fallback engaged, and the
  latency numbers describe the wrong provider.
