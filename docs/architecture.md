# FastRAG architecture

FastRAG is a production-oriented RAG service with source-grounded generation, calibrated
abstention, response caching, and traceable quality/cost signals. The deployment in this
repository is intentionally a hardened single-host Docker Compose topology; it is suitable
for a serious pilot or small production install, but it is not a highly available cluster.

## Request path

1. `POST /v1/query` or `POST /v1/query/stream` enters FastAPI with bearer-token auth.
2. The pipeline reads the active index snapshot from PostgreSQL: Qdrant collection name plus
   content version.
3. The exact cache is checked with a namespace derived from content version, embedding
   fingerprint, prompt version, generator model, and answer token limit.
4. The query is embedded using the same pinned dense model fingerprint recorded on the active
   index.
5. The semantic cache checks Redis vector similarity using the calibrated distance threshold.
6. Qdrant returns dense and BM25 candidates; FastRAG combines them with reciprocal rank fusion.
7. A cross-encoder reranker scores the candidates.
8. If the top reranker score is below calibration, FastRAG returns the standard no-answer.
9. The generator streams from an OpenAI-compatible `/v1/chat/completions` endpoint.
10. Sentence-level citation validation only releases complete sentences with valid
    `[C:chunk-id]` source markers.
11. The final answer, citations, cache status, stage timings, and trace metadata are returned.

Infrastructure failures are fail-closed. Retrieval, rerank, generation, and citation errors
return service errors, not fake no-answer responses. Cache and tracing failures are fail-open.

## Components

- `api`: FastAPI service, auth, query endpoints, admin endpoints, Prometheus metrics.
- `worker`: RQ ingestion worker that builds shadow Qdrant collections and activates aliases.
- `qdrant`: dense vector and sparse BM25 storage.
- `app-redis`: exact answer cache, semantic answer cache, and RQ queue storage.
- `postgres`: index registry and active index metadata.
- `langfuse-web` and `langfuse-worker`: LLM tracing, cost, and quality observability.
- `clickhouse`, `minio`, `langfuse-redis`: Langfuse backing services.
- `model-init`: one-shot tool for downloading and verifying local dense/reranker artifacts.
- `proxy`: Caddy TLS/routing for FastRAG and Langfuse.

## Data model and versioning

Each chunk stored in Qdrant includes `chunk_id`, `document_id`, text, title, source URI, page,
and metadata. The active index registry stores the embedding fingerprint, chunk settings,
content version, collection name, and index state.

Embedding models are never mixed. Changing dense model ID, revision, artifact checksum,
normalization, dimension, or query prefix creates a different embedding fingerprint and
requires a full re-index. Query-time startup validates that the active index fingerprint
matches the configured embedding fingerprint.

Cache namespaces include the active content version and generation-relevant configuration.
Content, prompt, model, or token-limit changes naturally miss old cache entries without
flushing Redis.

## Grounding and abstention

The system prompt requires context-only answers and citation markers. The pipeline also
enforces grounding mechanically:

- no candidates or low reranker score returns `I don't know based on the available sources.`;
- answer sentences are withheld until a valid source marker is seen;
- markers that do not refer to supplied chunks fail the request;
- infrastructure errors never become no-answer responses.

## Observability

Prometheus exposes request count, failure count, end-to-end latency, stage latency, and
time-to-first validated sentence. Langfuse receives traces with query hashes, stage metadata,
retrieved chunk IDs, scores, model identifiers, token usage, and latency. Raw questions and
raw documents are excluded unless `FASTRAG_TRACE_RAW_CONTENT=true` is explicitly configured.

## Deployment boundaries

The compose deployment does not autoscale and does not provide HA. The two-second latency SLO
is measured as p95 time to first validated answer sentence, not full answer completion. Final
capacity numbers must be accepted with corpus-specific golden evaluation and load testing on
the target hardware.
