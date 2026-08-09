# Deployment

Two supported topologies: Docker Compose on a single host (the `local` profile, and the
original production target), and free hosted tiers with the API on Render and one or both
Next.js frontends on Vercel (the `cloud` profile). This page covers the second; see
[local-setup.md](local-setup.md) for the first.

Frontends:

- [`website/`](../website/) - public landing (hero ask, chat answers, product narrative).
- [`web/`](../web/) - operator console (latency, strategy compare, CRAG/guardrail traces, bench).

## Before you deploy: ingest

Render's free tier has no background workers and an ephemeral filesystem, so the RQ ingestion
worker cannot run there. Ingestion is an offline step you run from your own machine against
the hosted Qdrant, Postgres, and embedding provider:

```bash
cp .env.cloud.example .env      # fill in every credential first
uv run python scripts/ingest-msmarco.py --rows-per-language 250 --max-chunks 90000
uv run python -m fastrag.calibrate \
  --golden eval/calibration.jsonl --cache-pairs eval/cache_pairs.jsonl
```

The result lives in Qdrant Cloud and Neon, so the Render service starts against a corpus
that already exists. `config/calibration.json` is baked into the image at build time - the
service refuses to start without it, deliberately.

Re-ingesting means re-running the script and redeploying. That is the cost of not having a
worker, and for a corpus that changes rarely it is the right trade.

## API on Render

[`render.yaml`](../render.yaml) is a Blueprint: point Render at the repo and it creates the
service. Free tier, Docker runtime, no disk, health check on `/health/ready`.

The Dockerfile binds `0.0.0.0:${PORT:-8000}` because Render assigns the port at runtime.
`FASTRAG_QUERY_API_KEY` and `FASTRAG_ADMIN_API_KEY` use `generateValue`, so Render mints them
and you copy the query key into Vercel. Everything marked `sync: false` is prompted for on
first deploy - those are the credentials from [providers.md](providers.md).

Two settings in the blueprint exist specifically because of the 512 MB / 0.1 CPU limit:

- `FASTRAG_SPARSE_RETRIEVAL_ENABLED=false`. The BM25 sparse leg comes from fastembed, which
  imports onnxruntime, which does not fit alongside everything else. Retrieval runs
  dense-only, costing some recall on rare terms and exact identifiers. Set it back to `true`
  on any paid instance to restore hybrid RRF.
- `FASTRAG_PROFILE=cloud`, which routes embedding and reranking to Jina rather than loading
  ONNX models into the instance.

Free services spin down after 15 minutes of inactivity and cold-start in several seconds.
Warm it before a demo.

## Frontends on Vercel

Deploy each app as its own Vercel project (or pick one). Set the Vercel **Root Directory**
to `website/` or `web/`. For the console, [`web/vercel.json`](../web/vercel.json) pins the
region to `sin1` (near a typical Render instance) and raises the proxy route duration limit
so long SSE streams are not cut off. Mirror that config on `website/` if you need the same
limits.

In each project set:

- `FASTRAG_API_URL` - your Render URL.
- `FASTRAG_QUERY_TOKEN` - the query key Render generated.

Neither is prefixed `NEXT_PUBLIC_`, deliberately.

The token stays server-side. `app/api/rag/[...path]/route.ts` in each app proxies browser
requests and attaches it, so it never reaches the client bundle. You do not need to add the
Vercel origin to `FASTRAG_CORS_ORIGINS` for proxy traffic. Set CORS only if the browser
should call the API directly.

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
curl -fsS https://your-api.onrender.com/health/ready
curl -fsS -H "Authorization: Bearer $KEY" https://your-api.onrender.com/build
```

`/build` reports the release, profile, and the three active providers, which is the quickest
way to confirm the deployed service is wired the way you think it is. Then drive a real voice
query through `website/` or `web/` and check that transcript, citations, guardrail decision,
CRAG trace, and Langfuse spans all appear.

## What this topology gives up

No HA, no autoscaling, cold starts, dense-only retrieval, and a 30 requests/minute LLM
ceiling. It is a demo and evaluation deployment, not a production one. The Compose topology
in [architecture.md](architecture.md) remains the production target, and the same code runs
on both.
