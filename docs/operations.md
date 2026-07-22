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

- Replace every value in `.env.example`.
- Keep query and admin API keys separate.
- Expose Grafana only behind authenticated infrastructure.
- Use TLS for public FastRAG and Langfuse endpoints.
- Keep `FASTRAG_TRACE_RAW_CONTENT=false` unless a controlled debugging session requires it.
- Protect vector DB, Redis, PostgreSQL, ClickHouse, and MinIO on private networks.
- Treat document deletion as delete chunks plus re-index or alias promotion to a clean index.

## Provider operations

Provider changes are release changes. Record model name, provider/gateway version, prompt
version, timeout, token cap, and cache namespace. Never silently fall back to a different model
inside the same release; it makes quality and cost regressions difficult to diagnose.

## Langfuse Cloud

To send traces to Langfuse Cloud instead of the bundled self-hosted Langfuse service, set the
cloud project credentials in the runtime environment:

```bash
LANGFUSE_PUBLIC_KEY=<cloud-public-key>
LANGFUSE_SECRET_KEY=<cloud-secret-key>
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

Do not commit real Langfuse secret keys to `.env.example`, docs, or CI logs. Verify credentials
with `langfuse.get_client().auth_check()` and flush a smoke trace before relying on dashboards.

## Cache operations

Normal content, model, prompt, and token-limit changes do not require flushing Redis because
they change the namespace. Only remove FastRAG cache prefixes when corrupt cache entries are
confirmed. Do not flush the whole application Redis; it also stores ingestion jobs.

## Dashboards

Track these panels at minimum:

- request rate and failure rate;
- p50/p95 TTFT and total latency;
- per-stage p95 latency;
- cache hit ratio split by exact and semantic;
- answer/no-answer rate;
- citation validation failures;
- provider token usage and cost;
- golden quality trend by release;
- active index/content version.
