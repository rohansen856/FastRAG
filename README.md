# FastRAG

FastRAG is a voice-enabled, multilingual, source-grounded RAG service built with FastAPI,
LlamaIndex, Qdrant, Redis, Langfuse, and RAGAS. It performs speech-to-text, input guardrails,
dense+BM25 retrieval with reciprocal rank fusion, cross-encoder reranking, corrective
retrieval, calibrated no-answer gating, sentence-level citation validation, and
exact/semantic response caching.

Every dependency sits behind a protocol, so the same code runs in two shapes selected by
`FASTRAG_PROFILE`:

- **`local`** — in-process ONNX models against containerised Qdrant, Redis, and Postgres.
  Nothing on the retrieval path crosses the internet, which is where the sub-200ms retrieval
  target is measured.
- **`cloud`** — hosted free tiers only (Qdrant Cloud, Jina, Sarvam, Groq, Neon, Redis Cloud,
  Langfuse Cloud), fitting Render's free web service with the UI on Vercel.

Both are benchmarked and both sets of numbers are published, clearly labelled. See
[latency.md](docs/latency.md).

## Request flow

1. Transcribe the audio upload, for voice requests.
2. Run text guardrails: empty, prompt injection, unsafe content, language gate.
3. Check the content-versioned exact cache.
4. Embed with the exact model fingerprint recorded for the active index.
5. Reject off-topic queries by comparing that embedding against the corpus centroid.
6. Check the calibrated Redis cosine-distance cache.
7. Run Qdrant dense and BM25 retrieval with RRF filtered by chunking strategy and language,
   then rerank the top 20 candidates.
8. Grade the top score with CRAG: generate directly, refine into sentence strips, or rewrite
   the query once and re-retrieve.
9. Return the standard no-answer response when the calibrated reranker gate fails.
10. Stream only complete sentences whose `[C:chunk-id]` markers refer to supplied context.
11. Trace stages, scores, model versions, token usage, cost inputs, and latency in Langfuse.

## Prerequisites

- Python 3.12 for local development
- Docker Engine with Compose v2
- A streaming, OpenAI-compatible Chat Completions endpoint
- Node 20+ for the web UI
- At least 24 vCPU, 64 GiB RAM, and NVMe storage for the stated 1M-chunk/20-QPS
  capacity-test envelope

## Development

```bash
uv sync --extra dev --extra ingest --extra eval
uv run pytest
uv run ruff check .
uv run mypy
```

Copy `.env.local.example` or `.env.cloud.example` to `.env` and replace every placeholder.
Both templates carry working defaults and a signup link for each hosted service. On the
local profile, pin the embedding and reranker revisions: mutable model names are not
sufficient production fingerprints.

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

For the multilingual MSMARCO-XI corpus, with a golden set derived from its own labels:

```bash
uv run python scripts/ingest-msmarco.py --rows-per-language 250 --max-chunks 90000
```

Every strategy in `FASTRAG_CHUNK_STRATEGIES` is indexed into the same collection under a
`strategy` payload field, so they can be compared at query time. See
[chunking.md](docs/chunking.md).

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

Add `strategy` to compare chunking strategies and `language` to filter to one language.
`GET /v1/strategies` reports what is indexed.

Answers include ordered citations with document, chunk, page, source URI, and excerpt, plus
the guardrail decision, CRAG trace, per-stage timings, and which provider generated the
answer. Dependency outages return an HTTP/SSE service error and are never represented as
“I don't know.” Cache, telemetry, and the optional safety classifier are fail-open;
retrieval, reranking, citation validation, and generation failures are fail-closed.

## Voice API

`POST /v1/voice/query` and `/v1/voice/query/stream` take a `multipart/form-data` audio upload,
transcribe it, and run the same pipeline. The streaming variant emits the transcript before
any answer token, so a misheard question is visible immediately.

```bash
curl -fsS -H "Authorization: Bearer $FASTRAG_QUERY_API_KEY" \
  -F file=@question.wav -F language=hi \
  https://localhost/v1/voice/query
```

`POST /v1/transcribe` does speech-to-text alone. Without an STT key configured, all three
return 503 and text queries are unaffected. See [voice.md](docs/voice.md).

## Web UI

```bash
cd web && npm install && npm run dev
```

Mic capture with a live waveform, streamed answers with citations, a per-stage latency panel,
side-by-side chunking-strategy comparison, the guardrail and CRAG decision trace, and the
benchmark dashboard. It proxies through a Next.js route so the API token stays server-side.

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
- [Providers](docs/providers.md): the two profiles, the free-tier matrix, hosted-model
  fingerprinting, and the non-silent fallback chain.
- [Local setup](docs/local-setup.md): Python setup, Docker Compose, ingestion, local query, and
  Ollama `llama3.2:latest` smoke testing.
- [Deployment](docs/deployment.md): Render and Vercel on free tiers, offline ingestion, and
  what the hosted topology gives up.
- [Voice](docs/voice.md): endpoints, Sarvam and ElevenLabs, transcribe versus translate, and
  audio format.
- [Chunking](docs/chunking.md): the six strategies, indexed versus generated text, and how to
  compare them honestly.
- [CRAG](docs/crag.md): reranker-band grading, strip refinement, capped query rewriting.
- [Guardrails](docs/guardrails.md): the cheapest-first input checks and what they do not do.
- [Latency](docs/latency.md): P50/P70/P100 per stage, and why STT and generation are reported
  separately from the 200ms retrieval target.
- [LLM providers](docs/llm-providers.md): OpenAI-compatible provider contract plus Ollama,
  OpenAI, Anthropic, Gemini, and gateway examples.
- [Benchmarking](docs/benchmarking.md): golden evaluation, calibration, load testing, and
  report interpretation.
- [Operations](docs/operations.md): release, backup, security, provider, cache, and dashboard
  procedures.

## Known boundaries

- Neither topology is HA or autoscaling; Compose is single-host and Render free is one
  instance that spins down after 15 minutes idle.
- The 200ms target covers the retrieval pipeline. It is met on the `local` profile and is not
  achievable over hosted providers, where three network hops sit on the retrieval path.
- The p95 SLO is time to the first validated answer sentence, not total completion time.
- The cloud profile runs dense-only retrieval, because onnxruntime does not fit in 512 MB.
- Hosted models cannot be checksum-pinned; the golden gate is what catches a silent change.
- Capacity and semantic thresholds are accepted only after corpus- and hardware-specific tests.
- Presidio integration is a deployment policy decision; blanket ingestion redaction can
  damage source meaning. Trace payloads are excluded by default.
