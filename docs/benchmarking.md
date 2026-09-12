# Benchmarking and evaluation

FastRAG has three separate gates: quality evaluation, latency/capacity testing, and the
per-stage latency benchmark. Passing one does not imply passing the others.

## Quality gate

Create `eval/golden.jsonl` with at least 200 reviewed records. At least 25 percent should be
unanswerable. Keep calibration data separate from regression data.

`scripts/ingest-msmarco.py` derives a golden set from the dataset's own labels: `is_selected`
marks the relevant passage and MS MARCO's "No Answer Present." marker supplies genuinely
unanswerable queries, targeting roughly 35 percent unanswerable. These are real labels rather
than fabricated ones, but they are the dataset's judgements, not yours - review them before
treating a release as gated.

`scripts/ingest-self.py` has no upstream labels to inherit, so it splits the work: the
generator writes the questions, and the chunker assigns `relevant_chunk_ids` from the section
each question came from. Unanswerable items are checked against the built index and dropped
when something answers them, because a file exclusion is not a semantic exclusion. Answerable
items are never filtered that way - pruning the ones retrieval missed is tuning the golden set
to pass its own gate. These are derived labels, not reviewed ones; read
[self-corpus.md](self-corpus.md) before gating a release on them.

`scripts/derive-eval.py` is the fallback when the generator quota is gone: it derives the
same records from headings, symbol names and docstrings. Those questions share vocabulary
with the chunks they point at, so the thresholds they produce are optimistic - treat them as
a bootstrap that lets a new index be served, and recalibrate from generated questions when
quota returns.

**Which corpus the published numbers come from.** The latency and quality figures in
[latency.md](latency.md) are measured on MSMARCO-XI. The self-corpus is around 650 chunks
under the `sentence` strategy, so retrieving the top 20 covers a large share of it and
recall@20 stops discriminating; treat it as a smoke test there and read MRR@5, faithfulness,
correctness and citation validity instead. Do not republish MSMARCO-XI numbers as if they
were measured on the self-corpus.

Keep the calibration split disjoint from the regression set. `scripts/ingest-self.py` splits
one pool by source document, stratified across languages and answerability, and fails early
if either split misses a bound its consumer requires - including the 40-negative floor that
`choose_gate`'s 0.05 false-answer constraint implies.

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

- `reranker_threshold` - the abstention gate, and CRAG's lower band.
- `crag_confident_threshold` - CRAG's upper band; above it, generate without correction.
- `cache_distance_threshold` - semantic cache cosine distance.
- `offtopic_threshold` - with the corpus centroid, the off-topic guardrail (cosine similarity,
  range **−1 to 1**; per-request override accepts the same range).

Recalibrate when you change dense embeddings, reranker, chunking, prompt, provider model,
profile, or corpus shape. The artifact records the `content_version` it was fitted against
and startup rejects a mismatch, so re-indexing without recalibrating is a 503 on
`/health/ready` rather than silently wrong gates. Switching profile changes the embedding and
reranking providers, so thresholds from one profile are meaningless on the other. Do not
loosen thresholds to make a release pass without adding hard negatives and reviewing the
error cases.

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

Run it once per profile; both results merge into `bench/results/summary.json`, which the `web/`
console dashboard and `GET /v1/bench` read. Full detail in [latency.md](latency.md).

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
