# Architecture diagrams

Interactive diagrams of FastRAG, generated with the archify diagram tool (v3.0.1) from the code
at commit `41815d0`. Every node cites the lines it is drawn from, and in the HTML viewer each
`SRC` badge links to those lines on GitHub. Open the `.html` files in a browser; each one is a
self-contained file.

| # | Diagram | Type | What it documents |
|---|---------|------|-------------------|
| 1 | [System context](01-system-context/system-context.html) | architecture | FastRAG as one system, with its users, CI, model providers, data stores and GitHub |
| 2 | [Containers (C4 level 2)](02-containers/containers.html) | architecture | website and console proxies, the API, the RQ worker, offline scripts, stores, providers |
| 3 | [API components](03-api-components/api-components.html) | architecture | routes, `QueryPipeline`, its collaborators and the `ports.py` adapters |
| 4a | [Streamed query](04a-query-sequence/query-sequence.html) | sequence | `/v1/query/stream` from the browser through guard, caches, retrieval, rerank, CRAG and the LLM |
| 4b | [Uploaded document](04b-upload-sequence/upload-sequence.html) | sequence | ingest, document-scoped query and delete for a session upload |
| 5 | [Data model](05-data-model/data-model.html) · [ERD](05-data-model/erd.md) | architecture + Mermaid | `index_manifests`, Qdrant collections and chunk points, Redis cache keys, calibration and eval files |
| 6 | [Data flow](06-dataflow/dataflow.html) | dataflow | offline indexing and eval-set generation, the online query path, what leaves the system |
| 7 | [Hosted deployment](07-deployment-hosted/deployment-hosted.html) | architecture | three Vercel projects, managed data services and model APIs (cloud profile) |
| 8a | [Index lifecycle](08a-index-lifecycle/index-lifecycle.html) | lifecycle | `index_manifests.state`: building → validated → active → retired / failed |
| 8b | [Query lifecycle](08b-query-lifecycle/query-lifecycle.html) | lifecycle | how one request ends: answered, cached, no_answer, refused or unavailable |
| 9 | [Release runbook](09-release-workflow/release-workflow.html) | workflow | ingest → calibrate → activate → deploy → golden and bench gates, with failure exits |
| 10 | [Compose network](10-network-compose/network-compose.html) | architecture | the self-hosted stack: Caddy ingress, one bridge network, ports, egress |

Archify has no ER notation, so the data model is drawn two ways: as an interactive entity map,
and as a Mermaid `erDiagram` with typed attributes and cardinalities in [`erd.md`](05-data-model/erd.md),
which GitHub renders inline. The hosted deployment (7) and the compose network (10) show the
two topologies FastRAG actually runs in; neither uses VPCs or subnets.

## Findings recorded on the diagrams

The analysis behind these diagrams turned up the following. They are recorded in the diagrams'
cards and have **not** been changed in code:

- `/metrics`, `/docs` and `/openapi.json` need no authentication, and nothing rate-limits
  inbound requests.
- `IndexBuilder` flips the Qdrant alias before `registry.activate()` runs.
- `register()` is an UPSERT, so rebuilding an existing version resets its row, even the active
  one, to `building`.
- `mark_failed` has no state guard.
- `cache_namespace()` does not include the reranker fingerprint or the calibration thresholds,
  so requests that override those without `skip_cache` share cache entries with default
  requests.
- `QueryTimings.cache_ms` is never set, and the `log_level` setting is never read.
- `Guardrails.check_safety_model` exists but nothing calls it.
- `compose.yaml` reads `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY`, while
  `.env.local.example` defines them with a `FASTRAG_` prefix.

## Regenerating

Each folder holds the archify source (`candidate.json`) next to its rendered HTML. After
editing a candidate, re-render it from the repository root; the `.evidence/` output is
gitignored:

```bash
node <archify>/bin/archify.mjs finalize <type> docs/diagrams/<folder>/candidate.json \
  docs/diagrams/<folder>/<name>.html --repo-root . --quality showcase \
  --out-dir docs/diagrams/<folder>/.evidence/<run> --json
```

When the code changes, update `meta.repository.revision` and recheck the cited line ranges;
the check gate verifies every citation against that commit.
