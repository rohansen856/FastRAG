# FastRAG operations runbook

## Triage order

1. Identify the affected release, active index/content version, prompt version, generator
   model, cache status, and Langfuse trace ID.
2. Check `/health/ready`, Prometheus alerts, queue depth, Qdrant health, Redis health, and
   managed-generator status.
3. Compare failure rate, TTFT, retrieval scores, abstention rate, tokens, and cost with the
   preceding release and index version.
4. Preserve traces and evaluation artifacts before rollback.

## Retriever or Qdrant failure

- Return `503`; do not translate infrastructure failure into a no-answer response.
- Cached hits remain serviceable because cache lookup precedes retrieval.
- Verify disk pressure, collection aliases, point count, and embedding fingerprint.
- If the new index is defective, repoint `kb_current` to the previous validated collection
  and activate its manifest. The resulting content version bypasses newer cache entries.

## Generator failure or rate limiting

- Cached responses and retrieval-only evaluations remain available.
- Verify endpoint region, timeout, concurrency and provider limits.
- A model change requires a configuration release and a new cache namespace. Never silently
  substitute an untracked fallback model.

## Quality regression

- Stop promotion when any golden gate fails.
- Segment Langfuse traces by release, model, prompt, index, and cache status.
- Inspect candidate Recall@20 before reranker MRR@5. Low recall indicates indexing/retrieval;
  good recall with poor MRR indicates reranking; good retrieval with poor faithfulness points
  to context selection or generation.
- Revert the application digest and Qdrant alias together when fingerprints changed.

## Latency or cost spike

- Split cache hit/miss traffic and inspect per-stage p95.
- Check model token counts, context size, provider TTFT, Qdrant disk latency, worker saturation,
  and cache hit ratio.
- Never loosen the semantic-cache threshold without rerunning hard-negative calibration.

## Backup and restore

- Back up PostgreSQL, Qdrant snapshots, Redis AOF, ClickHouse, MinIO, Compose configuration,
  calibration artifacts, and model checksums before migrations.
- Test restores on a separate host. A volume existing is not evidence that it is restorable.
- Retain at least the current and previous validated Qdrant collections.

## Cache handling

- Normal content/model/prompt changes invalidate by namespace and do not require a flush.
- Delete only the `fastrag:exact:*` and `fastrag:semantic:*` prefixes when corrupt cache data is
  confirmed. Do not flush the application Redis because it also contains ingestion jobs.

