# Local setup

This guide gets FastRAG running locally on the `local` profile: in-process ONNX embedding and
reranking, containerised Qdrant, Redis, and Postgres, and Ollama `llama3.2:latest` for
generation. Nothing on the retrieval path crosses the internet, which is what makes this the
rig the sub-200ms numbers in [latency.md](latency.md) are measured on.

For the hosted free-tier setup instead, see [deployment.md](deployment.md).

## Prerequisites

- Python 3.12
- `uv`
- Docker Engine with Compose v2
- Ollama running on the host
- `llama3.2:latest` installed locally

Verify Ollama from the host:

```bash
ollama list
ollama run llama3.2:latest "Reply with ok."
```

## Python development

Install local dependencies and run the fast test suite:

```bash
uv sync --extra dev --extra ingest --extra eval
uv run pytest
uv run ruff check .
uv run mypy
```

## Configure environment

Create `.env` from the local template, which is already configured for Ollama and the
in-process models:

```bash
cp .env.local.example .env
```

On Linux, Docker may need an explicit host gateway mapping for containers to reach the host
Ollama daemon. If `host.docker.internal` does not resolve in your Docker setup, use the host
gateway IP or run an OpenAI-compatible proxy container on the compose network.

Two things in that file are worth knowing about before you hit them:

- `FASTRAG_SEMANTIC_CACHE_ENABLED=false`, because the plain `redis:8` image has no RediSearch
  module. Exact caching still works. Swap in `redis/redis-stack` to enable it.
- Voice input needs a Sarvam key even here - no speech model runs in-process. Leave
  `FASTRAG_SARVAM_API_KEY` blank to run text-only; the `/v1/voice/*` endpoints then return
  503 and nothing else is affected. See [voice.md](voice.md).

The embedding model in this profile, `BAAI/bge-base-en-v1.5`, is English-only. To query the
multilingual MSMARCO-XI corpus, use the `cloud` profile or configure a multilingual local
model.

## Required calibration and model artifacts

Production startup requires `config/calibration.json`, pinned dense/reranker revisions, and
verified ONNX checksums. The example files are schema examples, not valid production gates.

Generate calibration from reviewed held-out data:

```bash
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl \
  --cache-pairs eval/cache_pairs.jsonl
```

Download and verify configured model artifacts:

```bash
docker compose --profile tools run --rm model-init
```

For a disposable local wiring test, you can copy the example calibration and use local model
paths/checksums only after accepting that quality gates are not meaningful:

```bash
cp config/calibration.example.json config/calibration.json
```

Do not ship with copied example calibration.

## Start services

```bash
docker compose build
docker compose up -d
```

This starts the API, worker, Qdrant, Redis, Postgres, Caddy, Prometheus, and Grafana.
Self-hosted Langfuse is not included: tracing points at Langfuse Cloud's free tier by
default, which avoids running ClickHouse, MinIO, and a second Redis on your laptop. Add
`--profile langfuse` and the commented block in `.env.local.example` if you want it locally.

Check health:

```bash
curl -fsS http://localhost/health/live
curl -fsS http://localhost/health/ready
```

## Ingest documents

Place extractable-text PDFs, Markdown, or plain text files under a local document directory and
ingest them:

```bash
uv run fastrag ingest docs/*.pdf docs/*.md docs/*.txt
```

The worker creates a shadow Qdrant collection, validates point count, swaps the `kb_current`
alias, and activates the manifest in PostgreSQL. Image-only PDFs fail until OCR is added
upstream.

Every strategy in `FASTRAG_CHUNK_STRATEGIES` is applied to each document and indexed into the
same collection under a `strategy` payload field, so they can be compared at query time. See
[chunking.md](chunking.md).

For the multilingual MSMARCO-XI corpus and a golden set derived from its own labels:

```bash
uv run python scripts/ingest-msmarco.py --rows-per-language 250 --max-chunks 90000
```

## Query locally

```bash
curl -fsS \
  -H "Authorization: Bearer $FASTRAG_QUERY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the refund period?"}' \
  http://localhost/v1/query
```

For streaming:

```bash
curl -N \
  -H "Authorization: Bearer $FASTRAG_QUERY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the refund period?"}' \
  http://localhost/v1/query/stream
```

Add `"strategy"` to compare chunking strategies, and `"language"` to filter to one language.

## Run the frontends

Both apps proxy through `/api/rag/[...path]` so `FASTRAG_QUERY_TOKEN` stays server-side.
`FASTRAG_CORS_ORIGINS` only matters if the browser calls the API directly.

**Landing (`website/`)** - marketing page with hero text/mic ask and chat answers:

```bash
cd website
cp .env.example .env.local     # FASTRAG_API_URL=http://localhost:8000
npm install
npm run dev                    # http://localhost:3000
```

**Console (`web/`)** - latency, strategies, CRAG/guardrails, bench dashboard:

```bash
cd web
cp .env.example .env.local     # FASTRAG_API_URL=http://localhost:8000
npm install
npm run dev -- -p 3001         # http://localhost:3001
```

Use port `8000` when the API is host uvicorn; use `http://localhost` (no port) when Compose
publishes through Caddy.

## Local Ollama smoke test

Use the adapter-level smoke script to verify that FastRAG can stream from the installed
`llama3.2:latest` model before starting the full stack:

```bash
uv run python scripts/smoke-ollama-provider.py
```

This checks the same OpenAI-compatible streaming path used by the production generator. It
does not require Qdrant, Redis, PostgreSQL, Langfuse, or calibration.

To verify FastAPI, the query pipeline, Ollama generation, citation validation, and Langfuse
trace flushing together without a production index, run:

```bash
LANGFUSE_PUBLIC_KEY=... \
LANGFUSE_SECRET_KEY=... \
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com \
uv run python scripts/smoke-local-e2e.py
```
