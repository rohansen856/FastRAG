# Operations guide

Use this guide with `docs/runbook.md`. The runbook is incident-oriented; this file covers
normal operating procedures.

## Release workflow

1. Build the image with a unique `FASTRAG_RELEASE`.
2. Pin dense and reranker revisions and artifact checksums.
3. Build or update the index in a shadow collection.
4. Validate point count and activate the Qdrant alias through the worker.
5. Run golden evaluation and load testing.
6. Compare Langfuse and Prometheus metrics with the previous release.
7. Promote the release by updating compose configuration and restarting services.

## Backups

Back up these together before migrations or index changes:

- PostgreSQL databases;
- Qdrant snapshots;
- Redis AOF for application cache/queue;
- ClickHouse and MinIO for Langfuse;
- `.env`, compose file, Caddy config, calibration files, prompt files;
- model artifact checksums and revisions.

Restores must be tested on a separate host. A successful file copy is not enough; verify that
FastRAG can read the active index snapshot, query Qdrant, and return cited answers.

## Security checklist

- Replace every value in `.env.local.example` or `.env.cloud.example`.
- Keep query and admin API keys separate.
- On Render, let `generateValue` mint the API keys and mark every credential `sync: false` so
  it is never committed to the blueprint.
- Keep the API token server-side in the Vercel proxy route; a token in the client bundle is a
  public token.
- Expose Grafana only behind authenticated infrastructure.
- Use TLS for public FastRAG and Langfuse endpoints.
- Keep `FASTRAG_TRACE_RAW_CONTENT=false` unless a controlled debugging session requires it.
- Protect vector DB, Redis, PostgreSQL, ClickHouse, and MinIO on private networks.
- Treat document deletion as delete chunks plus re-index or alias promotion to a clean index.

## Provider operations

Provider changes are release changes. Record model name, provider/gateway version, prompt
version, timeout, token cap, and cache namespace. Never *silently* fall back to a different
model; it makes quality and cost regressions difficult to diagnose.

The configured fallback provider is not a silent fallback. When it engages, the response
reports which provider actually answered in `generator_provider`, a `fastrag_fallbacks`
counter increments, and the switch is traced. Alert on that counter — a fallback that nobody
notices is exactly the situation this rule exists to prevent.

Changing embedding provider changes the embedding fingerprint and requires a re-index and a
recalibration. Startup validates this rather than letting it degrade quietly.

## Langfuse

Tracing defaults to Langfuse Cloud's free tier. Set the project credentials in the runtime
environment:

```bash
FASTRAG_LANGFUSE_PUBLIC_KEY=<cloud-public-key>
FASTRAG_LANGFUSE_SECRET_KEY=<cloud-secret-key>
FASTRAG_LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

The application publishes these under the bare `LANGFUSE_*` names the SDK reads, so the
prefixed variables are the only ones you need to set. Leave the keys blank to disable
tracing; the code is fail-open and the service is unaffected.

To self-host Langfuse instead, run `docker compose --profile langfuse up -d` and point
`LANGFUSE_BASE_URL` at `http://langfuse-web:3000`. That profile adds ClickHouse, MinIO, and a
second Redis, all of which then need backing up.

Do not commit real Langfuse secret keys to the env examples, docs, or CI logs. Verify
credentials with `langfuse.get_client().auth_check()` and flush a smoke trace before relying
on dashboards.

## Cache operations

Normal content, model, prompt, chunking-strategy, profile, and token-limit changes do not
require flushing Redis because they all change the namespace. Only remove FastRAG cache
prefixes when corrupt cache entries are confirmed. Do not flush the whole application Redis;
it also stores ingestion jobs.

The semantic cache needs the RediSearch module. Where it is unavailable — Upstash does not
support `FT.CREATE` — set `FASTRAG_SEMANTIC_CACHE_ENABLED=false`; exact caching is unaffected.
The adapter also degrades to exact-only on its own if the module turns out to be missing at
runtime, so a provider change cannot take the service down, but it will quietly cost you the
semantic hit rate. Check the startup logs after changing Redis provider.

Refused responses from guardrails are never cached, so tightening or relaxing a rule takes
effect on the next request without a flush.

## Dashboards

Track these panels at minimum:

- request rate and failure rate;
- p50/p95 TTFT and total latency;
- per-stage p95 latency;
- cache hit ratio split by exact and semantic;
- answer/no-answer rate;
- citation validation failures;
- provider token usage and cost;
- guardrail blocks by rule and CRAG actions by action;
- provider retries, circuit-breaker trips, and generator fallbacks;
- golden quality trend by release;
- active index/content version.
