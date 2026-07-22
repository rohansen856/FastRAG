# Benchmarking and evaluation

FastRAG has two separate gates: quality evaluation and latency/capacity testing. Passing one
does not imply passing the other.

## Quality gate

Create `eval/golden.jsonl` with at least 200 reviewed records. At least 25 percent should be
unanswerable. Keep calibration data separate from regression data.

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

Generate no-answer and semantic-cache thresholds from held-out data:

```bash
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl \
  --cache-pairs eval/cache_pairs.jsonl
```

Recalibrate when you change dense embeddings, reranker, chunking, prompt, provider model,
or corpus shape. Do not loosen thresholds to make a release pass without adding hard negatives
and reviewing the error cases.

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

## What to record

Every benchmark report should include:

- git or image release;
- active content version and Qdrant collection;
- dense model fingerprint and reranker fingerprint;
- provider base URL class and model name;
- prompt version and answer token limit;
- hardware profile;
- corpus size and chunk count;
- QPS, duration, concurrency shape, cache hit ratio;
- p50/p95 TTFT, p95 stage latencies, failure rate;
- golden quality metrics and citation failure count.

## Interpreting failures

- Low Recall@20: ingestion, chunking, dense/BM25 retrieval, or embedding mismatch.
- Good Recall@20 but low MRR@5: reranker quality, candidate count, or threshold calibration.
- Good retrieval but low faithfulness: prompt/provider behavior or context budget.
- Citation failures: provider did not obey marker format or answer used unsupported claims.
- High TTFT with cache misses: provider generation or reranker latency.
- High TTFT with cache hits: Redis/network issues or response validation overhead.
- Cost spike: cache hit ratio drop, answer length growth, provider price change, or trace volume.
