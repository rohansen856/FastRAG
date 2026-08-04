# FastRAG architecture

FastRAG is a voice-enabled, multilingual RAG service with source-grounded generation,
corrective retrieval, input guardrails, calibrated abstention, response caching, and
traceable quality/cost signals.

Every external dependency sits behind a protocol in [`ports.py`](../src/fastrag/ports.py), so
the same code runs in two deployment shapes: a hardened single-host Docker Compose topology
with in-process models, and a fully hosted free-tier deployment on Render and Vercel.
`FASTRAG_PROFILE` selects between them. See [providers.md](providers.md) and
[deployment.md](deployment.md).

## Request path

1. `POST /v1/query`, `/v1/query/stream`, or one of the `/v1/voice/*` endpoints enters FastAPI
   with bearer-token auth.
2. Voice requests transcribe the upload first; the transcript is carried through the rest of
   the pipeline and returned. See [voice.md](voice.md).
3. Text guardrails run: empty input, prompt injection, unsafe content, and language gate.
   Blocked input is refused here, before any provider call. See [guardrails.md](guardrails.md).
4. The pipeline reads the active index snapshot from PostgreSQL: Qdrant collection name plus
   content version.
5. The exact cache is checked with a namespace derived from content version, embedding
   fingerprint, chunking strategy, retrieval profile, prompt version, generator model, and
   answer token limit.
6. The query is embedded using the same pinned dense model fingerprint recorded on the active
   index.
7. The vector guardrail compares the query embedding against the corpus centroid, refusing
   off-topic queries for the cost of a dot product.
8. The semantic cache checks Redis vector similarity using the calibrated distance threshold.
9. Qdrant returns dense and BM25 candidates filtered by chunking strategy and language;
   FastRAG combines them with reciprocal rank fusion.
10. A cross-encoder reranker scores the candidates.
11. CRAG grades the top score against two calibrated bands and either generates directly,
    refines the context into sentence strips, or rewrites the query once and re-retrieves.
    See [crag.md](crag.md).
12. If the top score is still below calibration, FastRAG returns the standard no-answer.
13. The generator streams from an OpenAI-compatible `/v1/chat/completions` endpoint, wrapped
    in the provider harness: retries with jittered backoff, circuit breaker, shared deadline,
    and an explicitly reported fallback provider.
14. Sentence-level citation validation only releases complete sentences with valid
    `[C:chunk-id]` source markers.
15. The final answer, citations, cache status, stage timings, guardrail decision, CRAG trace,
    transcript, and generating provider are returned.

Infrastructure failures are fail-closed. Retrieval, rerank, generation, and citation errors
return service errors, not fake no-answer responses. Cache, tracing, and the optional model
safety classifier are fail-open.

## Components

- `api`: FastAPI service, auth, query endpoints, admin endpoints, Prometheus metrics.
- `worker`: RQ ingestion worker that builds shadow Qdrant collections and activates aliases.
- `qdrant`: dense vector and sparse BM25 storage.
- `app-redis`: exact answer cache, semantic answer cache, and RQ queue storage.
- `postgres`: index registry and active index metadata.
- `model-init`: one-shot tool for downloading and verifying local dense/reranker artifacts.
- `proxy`: Caddy TLS/routing for FastRAG and Langfuse.
- `langfuse-web`, `langfuse-worker`, `clickhouse`, `minio`, `langfuse-redis`: self-hosted
  tracing, behind the optional `langfuse` compose profile. Langfuse Cloud's free tier is the
  default and needs none of them.

In the hosted deployment the API is the only running service; Qdrant, Redis, Postgres,
embedding, reranking, speech-to-text, generation, and tracing are all managed providers, and
ingestion is an offline script rather than the worker.

## Data model and versioning

Each chunk stored in Qdrant includes `chunk_id`, `document_id`, text, title, source URI, page,
chunking `strategy`, detected `language`, position, and an optional `context_text` for
strategies that generate from a wider span than they index. `strategy` and `language` are
payload-indexed so they can be used as query filters. The active index registry stores the
embedding fingerprint, chunk settings, chunking strategies, languages, chunk count, content
version, collection name, and index state.

Embedding models are never mixed. Changing dense model ID, revision, artifact checksum,
normalization, dimension, or query prefix creates a different embedding fingerprint and
requires a full re-index - including switching profile, since that changes the embedding
provider. Query-time startup validates that the active index fingerprint matches the
configured embedding fingerprint. Hosted models have no local file to checksum, so their
fingerprint component is `provider:model` at revision `hosted-api`.

Cache namespaces include the active content version, chunking strategy, retrieval profile,
and generation-relevant configuration. Content, prompt, model, strategy, or token-limit
changes naturally miss old cache entries without flushing Redis, so an A/B comparison between
chunking strategies cannot silently share results.

## Grounding and abstention

The system prompt requires context-only answers and citation markers. The pipeline also
enforces grounding mechanically:

- no candidates or low reranker score returns `I don't know based on the available sources.`;
- answer sentences are withheld until a valid source marker is seen;
- markers that do not refer to supplied chunks fail the request;
- CRAG abstains rather than answering when a rewrite fails or its retry still scores low;
- input guardrails produce a distinct `REFUSED` outcome, which is never cached;
- infrastructure errors never become no-answer responses.

Sentence boundaries are detected with a terminator set covering Indic punctuation as well as
ASCII. An English-only splitter would treat a Hindi answer as a single sentence and defeat
sentence-level citation streaming entirely.

## Observability

Prometheus exposes request count, failure count, end-to-end latency, stage latency,
time-to-first validated sentence, provider retries, circuit-breaker trips, generator
fallbacks, guardrail blocks by rule, and CRAG actions by action. Langfuse receives traces
with query hashes, stage metadata, retrieved chunk IDs, scores, model identifiers, token
usage, and latency. Raw questions and raw documents are excluded unless
`FASTRAG_TRACE_RAW_CONTENT=true` is explicitly configured.

## Deployment boundaries

Neither topology autoscales or provides HA. The two-second latency SLO is measured as p95
time to first validated answer sentence, not full answer completion; the separate sub-200ms
retrieval-pipeline target is measured on the `local` profile and is not achievable over
hosted providers, which [latency.md](latency.md) reports rather than papers over. Final
capacity numbers must be accepted with corpus-specific golden evaluation and load testing on
the target hardware.
