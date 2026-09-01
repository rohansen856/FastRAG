# Query trace and pipeline experiments

Every `QueryResponse` includes an optional `trace` object with stage timings, retrieval
funnel data, calibration thresholds used, model fingerprints, and `overrides_applied` when
per-request config was changed. The marketing site exposes this on `/query` for the latest
browser-session run.

## Response shape

`trace` is populated on both `POST /v1/query` and `POST /v1/query/stream` (inside the
`final` SSE event). Highlights:

| Field | Meaning |
|-------|---------|
| `stages` | Ordered pipeline stages (`text_guard`, caches, `retrieve`, `rerank`, `crag`, `generate`, …) with `status`, `duration_ms`, and optional `detail`. |
| `retrieved` / `reranked` / `contexts` | Chunk funnel with scores and excerpts. |
| `cited_chunk_ids` | Chunks that survived citation validation. |
| `reranker_threshold`, `crag_confident_threshold`, `offtopic_threshold` | Effective calibration values for this run. |
| `candidate_k`, `context_top_k` | Retrieval limits used. |
| `generator_model`, `embedding_fingerprint`, `reranker_fingerprint` | Model/index identity. |
| `overrides_applied` | Redacted copy of request overrides (`llm.api_key` → `***`). |
| `abstention_reason` | Set when outcome is `no_answer`. |

Guardrail and CRAG decisions remain on the top-level `guardrail` and `crag` fields; the trace
stages mirror where they fired.

## Per-request overrides (`overrides`)

Pass an `overrides` object on the query body to experiment without changing server config.
Only fields you set are applied; omitted fields keep deployment defaults.

```json
{
  "query": "How does CRAG decide to rewrite a query?",
  "strategy": "sentence",
  "language": "en",
  "overrides": {
    "skip_cache": true,
    "crag_enabled": false,
    "candidate_k": 12,
    "context_top_k": 2,
    "reranker_threshold": 0.25,
    "crag_confident_threshold": 0.55,
    "offtopic_threshold": -0.12,
    "llm": {
      "model": "openai/gpt-oss-20b",
      "base_url": "https://api.openai.com/v1",
      "api_key": "sk-…",
      "max_tokens": 512
    }
  }
}
```

| Override | Effect |
|----------|--------|
| `skip_cache` | Bypass exact and semantic cache read/write for this request. |
| `crag_enabled` | Force CRAG on or off (when the deployment has CRAG available). |
| `candidate_k` | Cap dense/BM25 candidates before rerank (1–100). |
| `context_top_k` | Chunks passed to generation after rerank (1–20). |
| `reranker_threshold` | Abstention gate and CRAG lower band (0–1). |
| `crag_confident_threshold` | CRAG upper band (0–1). |
| `offtopic_threshold` | Vector guardrail cosine gate (**−1 to 1**; calibration often yields small negative values). |
| `llm.*` | Request-scoped generator endpoint/model/tokens. Requires a configured base URL on the server for override routing to activate. |

`strategy`, `language`, and `document_ids` stay top-level query fields (not inside
`overrides`). `language` is reduced to its ISO 639-1 primary subtag before it reaches Qdrant,
so `hi-IN` and `hi` both match the `hi` chunks; the UIs send the regional form because that is
what Sarvam's speech models want.

### Gating

Overrides are **allowed** when `FASTRAG_ALLOW_QUERY_OVERRIDES=true`, or when that variable
is unset and `FASTRAG_ENVIRONMENT=development`.

Example defaults:

- [`.env.local.example`](../.env.local.example) - `FASTRAG_ALLOW_QUERY_OVERRIDES=true`
- [`.env.cloud.example`](../.env.cloud.example) - `FASTRAG_ALLOW_QUERY_OVERRIDES=false`

Production deployments should keep the cloud default (`false`). Requests with any override
field return `422` with `query overrides are disabled on this deployment` when blocked.
Per-request LLM API keys are never stored in the trace (redacted in `overrides_applied`).

## Website `/query` page

[`website/`](../website/) saves the latest hero answer trace in `sessionStorage` and links to
`/query`:

1. Run a question on the home page (text or voice).
2. Open **View pipeline trace** (or go to `/query` directly).
3. Use the **Experiment** panel to edit strategy, language, cache, CRAG, K limits, thresholds,
   and optional LLM settings, then **Re-run pipeline** (streams like the hero).
4. Toggle **Original run** / **Latest re-run** to compare traces.
5. **Reset to original** restores the baseline trace view and form; the panel stays open.

Traces are session-only (not persisted server-side). `/query/[queryId]` redirects to `/query`
because only the latest trace is kept in this browser tab.

Components live under `website/components/query-trace/`; form logic is in
`website/lib/query-config.ts` (`buildOverrides` only sends fields that differ from the
original trace, using epsilon comparison for float thresholds).

## Smoke tests

```bash
# API + website proxy override check (API must be up; set FASTRAG_QUERY_TOKEN if needed)
FASTRAG_API_URL=http://localhost:8001 uv run python scripts/e2e_query_overrides.py

# Frontend buildOverrides unit check
cd website && npx tsx scripts/check-build-overrides.ts
```

## Related docs

- [Guardrails](guardrails.md) - off-topic threshold semantics.
- [Benchmarking](benchmarking.md) - how calibration sets threshold values.
- [CRAG](crag.md) - what `crag_enabled` and confident threshold control.
- [Architecture](architecture.md) - where trace is built in the pipeline.
