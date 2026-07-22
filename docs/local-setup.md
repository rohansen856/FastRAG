# Local setup

This guide gets FastRAG running locally with Ollama `llama3.2:latest` as the generation
provider. The same service code is used in production; local setup mainly swaps the hosted
LLM endpoint for Ollama.

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

Create `.env` from the template:

```bash
cp .env.example .env
```

For local Ollama, keep:

```bash
FASTRAG_LLM_BASE_URL=http://host.docker.internal:11434/v1
FASTRAG_LLM_API_KEY=ollama
FASTRAG_LLM_MODEL=llama3.2:latest
```

On Linux, Docker may need an explicit host gateway mapping for containers to reach the host
Ollama daemon. If `host.docker.internal` does not resolve in your Docker setup, use the host
gateway IP or run an OpenAI-compatible proxy container on the compose network.

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
