# FastRAG

FastRAG is a source-grounded, stateless RAG service built with FastAPI, LlamaIndex,
Qdrant, Redis, Langfuse, and RAGAS. It performs English dense+BM25 retrieval, reciprocal
rank fusion, cross-encoder reranking, calibrated no-answer gating, sentence-level citation
validation, and exact/semantic response caching.

The production topology is a hardened single-host Docker Compose deployment. It includes
backups and index rollback, but it is not highly available and does not autoscale.

## Request flow

1. Check the content-versioned exact cache.
2. Embed with the exact model fingerprint recorded for the active index.
3. Check the calibrated Redis cosine-distance cache.
4. Run Qdrant dense and BM25 retrieval with RRF, then rerank the top 20 candidates.
5. Return the standard no-answer response when the calibrated reranker gate fails.
6. Stream only complete sentences whose `[C:chunk-id]` markers refer to supplied context.
7. Trace stages, scores, model versions, token usage, cost inputs, and latency in Langfuse.

## Prerequisites

- Python 3.12 for local development
- Docker Engine with Compose v2
- A streaming, OpenAI-compatible Chat Completions endpoint
- At least 24 vCPU, 64 GiB RAM, and NVMe storage for the stated 1M-chunk/20-QPS
  capacity-test envelope

## Development

```bash
uv sync --extra dev --extra ingest --extra eval
uv run pytest
uv run ruff check .
uv run mypy
```

Copy `.env.example` to `.env`, replace every placeholder, and pin the embedding and
reranker revisions. Mutable model names are not sufficient production fingerprints.

The service deliberately refuses to start without `config/calibration.json`. Generate it
from at least 30 held-out answerable/unanswerable questions and 30 labeled semantic-cache
pairs:

```bash
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl \
  --cache-pairs eval/cache_pairs.jsonl
```

Do not copy values from `config/calibration.example.json`; they are schema examples only.

Download the dense and reranker repositories at the exact configured commits, then verify
their ONNX checksums before starting production services:

```bash
docker compose --profile tools run --rm model-init
```

## Start and ingest

```bash
docker compose build
docker compose --profile tools run --rm model-init
docker compose up -d
uv run fastrag ingest docs/*.pdf docs/*.md docs/*.txt
```

The CLI copies documents to the durable document volume and builds a shadow Qdrant
collection. The worker checks point counts, marks the manifest validated, swaps
`kb_current`, and only then marks the version active. Query-time cache namespaces read the
active content version from PostgreSQL on every request.

The equivalent administration API uses a separate bearer key:

```bash
curl -fsS -H "Authorization: Bearer $FASTRAG_ADMIN_API_KEY" \
  -F document_id=refund-policy -F file=@refund-policy.pdf \
  https://localhost/v1/admin/documents
```

Supported input is PDF with extractable text, Markdown, and plain text. Image-only PDFs
fail with an OCR-required error; OCR is intentionally outside v1.

## Query API

`POST /v1/query` returns a complete JSON response. `POST /v1/query/stream` returns SSE
events named `meta`, `answer_chunk`, `final`, and `error`.

```bash
curl -fsS -H "Authorization: Bearer $FASTRAG_QUERY_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"query":"What is the refund period?"}' \
  https://localhost/v1/query
```

Answers include ordered citations with document, chunk, page, source URI, and excerpt.
Dependency outages return an HTTP/SSE service error and are never represented as “I don't
know.” Cache and telemetry failures are fail-open; retrieval, reranking, citation validation,
and generation failures are fail-closed.

## Evaluation gate

`eval/golden.jsonl` is intentionally not fabricated by this scaffold. Before a release,
create at least 200 reviewed, version-controlled records using the schema demonstrated by
`eval/golden.example.jsonl`; at least 25% must be unanswerable. Keep calibration records
separate from regression records.

Run the complete gate against the production configuration:

```bash
uv run python scripts/check-golden.py
uv run python -m fastrag.evaluation \
  --dataset eval/golden.jsonl \
  --api-url https://localhost \
  --output eval/results/report.json
```

The command exits nonzero unless Recall@20 ≥ 0.95, reranked MRR@5 ≥ 0.85,
faithfulness/relevancy/correctness ≥ 0.90, false-answer rate ≤ 0.05, and citation validity
equals 1.0. It uses deterministic ID metrics plus RAGAS judges with the pinned managed model.
The PR workflow requires a protected self-hosted `fastrag-eval` runner because model weights,
the corpus, provider credentials, and a representative index cannot safely run on an
untrusted hosted runner. Configure the workflow's dense/reranker model-path variables to
the checksum-verified snapshots installed on that runner.

## Operations

- FastRAG metrics: `https://<api-domain>/metrics`
- Langfuse: `https://<langfuse-domain>`
- Grafana is internal by default; expose it only behind authenticated infrastructure.
- Raw questions and documents are excluded from tracing. Query hashes, retrieved chunk IDs,
  ranks, scores, versions, token usage, and timings are retained.
- Prometheus alerts when TTFT p95 exceeds two seconds for ten minutes or failures spike.

See [the runbook](docs/runbook.md) for backup, rollback, outage, quality, and cost incidents.

## Documentation

- [Architecture](docs/architecture.md): request flow, components, versioning, grounding, and
  deployment boundaries.
- [Local setup](docs/local-setup.md): Python setup, Docker Compose, ingestion, local query, and
  Ollama `llama3.2:latest` smoke testing.
- [LLM providers](docs/llm-providers.md): OpenAI-compatible provider contract plus Ollama,
  OpenAI, Anthropic, Gemini, and gateway examples.
- [Benchmarking](docs/benchmarking.md): golden evaluation, calibration, load testing, and
  report interpretation.
- [Operations](docs/operations.md): release, backup, security, provider, cache, and dashboard
  procedures.

## Known boundaries

- Compose is single-host and therefore cannot meet an HA SLO.
- The p95 target is time to the first validated answer sentence, not total completion time.
- Capacity and semantic thresholds are accepted only after corpus- and hardware-specific tests.
- Presidio integration is a deployment policy decision; blanket ingestion redaction can
  damage source meaning. Trace payloads are excluded by default.
