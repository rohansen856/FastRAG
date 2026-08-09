# FastRAG - agent notes

Voice-enabled, multilingual, source-grounded RAG. Python API under `src/fastrag/`; two Next.js
frontends; docs in `docs/`.

## Layout

| Path | Role |
|------|------|
| `src/fastrag/` | FastAPI pipeline: retrieval, CRAG, guardrails, cache, STT, harness |
| `scripts/` | Ingest, calibrate, bench, golden gate, smoke tests |
| `website/` | Marketing landing (hero ask + chat). Dev: `:3000` |
| `web/` | Operator console (latency, strategies, CRAG, bench). Dev: `:3001` |
| `docs/` | Architecture, providers, deploy, voice, chunking, CRAG, etc. |
| `compose.yaml` / `render.yaml` | Local stack vs Render Blueprint |
| `.env.local.example` / `.env.cloud.example` | Profile templates - never commit real `.env` |

## Profiles

`FASTRAG_PROFILE=local` - ONNX embed/rerank, Compose Qdrant/Redis/Postgres; sub-200ms retrieval target.
`FASTRAG_PROFILE=cloud` - Jina, Qdrant Cloud, Groq, Sarvam, Neon, Redis Cloud, Langfuse Cloud; dense-only on free Render.

Service refuses to start without real `config/calibration.json` (not the example schema).

## Frontends

Both apps use `FASTRAG_API_URL` + `FASTRAG_QUERY_TOKEN` (server-only) and
`app/api/rag/[...path]/route.ts`. Do not use `NEXT_PUBLIC_` for the token.
Normalize SSE `\r\n` → `\n` in client parsers. Mic audio is re-encoded to 16 kHz mono WAV in
`lib/audio.ts` in each app.

## Conventions

- Protocols in `ports.py`; swap adapters, do not fork the pipeline for providers.
- Fail-closed on retrieval/rerank/generation/citations; fail-open on cache/telemetry/optional safety classifier.
- Do not invent golden/calibration data; do not commit secrets, calibration outputs, or model weights.
- Prefer editing existing docs over adding parallel README copies.
- `web/AGENTS.md` and `website/AGENTS.md` may be rewritten by `next dev`; keep durable guidance here.

## Quick checks

```bash
uv sync --extra dev --extra ingest --extra eval
uv run pytest && uv run ruff check . && uv run mypy
```
