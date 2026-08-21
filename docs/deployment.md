# Deployment

Two supported topologies: Docker Compose on a single host (the `local` profile), and free
hosted tiers with the **cloud** profile (hosted Qdrant/Jina/Groq/etc.). For cloud, the API
can run on **Vercel** (Python FastAPI function) or **Render** (Docker); frontends stay on
Vercel. This page covers hosted deploy; see [local-setup.md](local-setup.md) for Compose.

Frontends (separate Vercel projects; Root Directory = app folder):

- [`website/`](../website/) — public landing (hero ask, chat answers, product narrative).
- [`web/`](../web/) — operator console (latency, strategy compare, CRAG/guardrail traces, bench).

## Before you deploy: ingest

Neither Vercel nor Render free has an RQ worker or durable disk for ingestion. Run ingest and
calibrate from your machine against hosted Qdrant, Postgres, and embedding:

```bash
cp .env.cloud.example .env      # fill in every credential first
uv run python scripts/ingest-msmarco.py --rows-per-language 250 --max-chunks 90000
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl --cache-pairs eval/cache_pairs.jsonl
```

The index lives in Qdrant Cloud + Neon. The API only needs `config/calibration.json` at
startup (it refuses to boot without it). Re-ingest offline when the corpus changes.

## API on Vercel

Use a **separate** Vercel project with **Root Directory** = repository root (not `web/` /
`website/`). Vercel detects FastAPI from `pyproject.toml`; the entrypoint is declared there:

```toml
[tool.vercel]
entrypoint = "src.fastrag.api:app"
```

Root [`vercel.json`](../vercel.json) sets `maxDuration` to 300s on `src/fastrag/api.py` so
voice + SSE streams are not cut off early, and excludes the Next.js trees from the Python
bundle.

1. Import the Git repo as a new Vercel project (root directory `.`).
2. Copy every variable from `.env.cloud.example` / your local `.env` into Project →
   Environment Variables. Minimum for a working boot:
   - `FASTRAG_PROFILE=cloud`
   - `FASTRAG_ENVIRONMENT=production` (or `development`)
   - `FASTRAG_SPARSE_RETRIEVAL_ENABLED=false`
   - `FASTRAG_QUERY_API_KEY`, `FASTRAG_ADMIN_API_KEY`
   - `FASTRAG_QDRANT_URL`, `FASTRAG_QDRANT_API_KEY`
   - `FASTRAG_JINA_API_KEY`
   - `FASTRAG_LLM_BASE_URL`, `FASTRAG_LLM_API_KEY`, `FASTRAG_LLM_MODEL`
   - `FASTRAG_DATABASE_URL`, `FASTRAG_REDIS_URL`
   - `FASTRAG_CALIBRATION_JSON` — paste the full JSON from local
     `config/calibration.json` (gitignored; without this, startup fails)
3. Redeploy. Open `/health/ready` — on failure it returns `{"status":"not_ready","error":"..."}`
   instead of a blank 500. Fix whatever `error` names, then confirm `/build` with the admin key.

Point frontend projects at this URL via `FASTRAG_API_URL` (and `FASTRAG_QUERY_TOKEN` =
`FASTRAG_QUERY_API_KEY`).

Cold starts on Fluid compute rebuild the pipeline in lifespan; first request after idle is
slower. Python `excludeFiles` in root `vercel.json` keeps `web/` / `website/` out of the
function bundle; they must still exist in the Git upload for the frontend projects.

## API on Render (alternative)

[`render.yaml`](../render.yaml) is a Blueprint: free Docker web service, health check
`/health/ready`, binds `0.0.0.0:$PORT`. `FASTRAG_QUERY_API_KEY` / `FASTRAG_ADMIN_API_KEY`
use `generateValue`; credentials marked `sync: false` are prompted on first deploy.
`config/calibration.json` is `COPY`’d only if present in the build context — it is
gitignored, so production must set `FASTRAG_CALIBRATION_JSON` (declared in
[`render.yaml`](../render.yaml)). The image entrypoint writes that env var to
`/app/config/calibration.json` before uvicorn starts.

Blueprint defaults: `FASTRAG_PROFILE=cloud`, `FASTRAG_SPARSE_RETRIEVAL_ENABLED=false`.
Free instances spin down after ~15 minutes idle.

## Frontends on Vercel

Use **separate** Vercel projects from the FastAPI API project (do not set Root Directory to
`.` for these).

| Project | Root Directory | Role |
|---------|----------------|------|
| Landing | `website/` | Public marketing site + hero ask / chat |
| Console (optional) | `web/` | Operator latency / CRAG / bench UI |

Do not put `web/` or `website/` in the root [`.vercelignore`](../.vercelignore) — that file
applies to every project in the monorepo and would strip the Next.js app before install.

Each has its own `vercel.json` (`maxDuration` 60s on the RAG proxy for SSE). In each project set:

- `FASTRAG_API_URL` — your FastAPI Vercel URL (e.g. `https://fast-rag-….vercel.app`).
- `FASTRAG_QUERY_TOKEN` — same value as `FASTRAG_QUERY_API_KEY` on the API.

Neither is prefixed `NEXT_PUBLIC_`. Proxy route `app/api/rag/[...path]/route.ts` keeps the
token server-side, so the landing origin does **not** need to be in `FASTRAG_CORS_ORIGINS`
unless you bypass the proxy and call the API from the browser.

## Self-hosted Langfuse is opt-in

`docker compose up` no longer starts Langfuse. Tracing points at Langfuse Cloud's free tier
by default, which needs no ClickHouse, no MinIO, and no second Redis. To run it yourself:

```bash
docker compose --profile langfuse up -d
```

and set the commented block at the bottom of `.env.local.example`, plus
`LANGFUSE_BASE_URL=http://langfuse-web:3000`. Nothing else changes; the application code
is identical either way.

## Verifying a deploy

```bash
curl -fsS https://your-api.vercel.app/health/ready
curl -fsS -H "Authorization: Bearer $KEY" https://your-api.vercel.app/build
# or https://your-api.onrender.com/...
```

`/build` reports the release, profile, and the three active providers, which is the quickest
way to confirm the deployed service is wired the way you think it is. Then drive a real voice
query through `website/` or `web/` and check that transcript, citations, guardrail decision,
CRAG trace, and Langfuse spans all appear.

## What this topology gives up

No HA for Compose; cold starts on free hosts; dense-only when sparse is off; LLM free-tier
rate limits. Demo and evaluation, not production HA. Same application code on local and cloud.
