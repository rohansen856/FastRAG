# Providers and profiles

Every external dependency sits behind a protocol in [`src/fastrag/ports.py`](../src/fastrag/ports.py),
so swapping a provider is a wiring change in [`src/fastrag/bootstrap.py`](../src/fastrag/bootstrap.py)
rather than a rewrite. `FASTRAG_PROFILE` picks a coherent default set; individual
`FASTRAG_*_PROVIDER` variables override any single choice.

## The two profiles

| | `local` | `cloud` |
|---|---|---|
| Embedding | FastEmbed `BAAI/bge-base-en-v1.5`, in-process ONNX | Jina `jina-embeddings-v3` |
| Reranking | FastEmbed `Xenova/ms-marco-MiniLM-L-6-v2`, in-process | Jina `jina-reranker-v2-base-multilingual` |
| Vector DB | Qdrant container | Qdrant Cloud free |
| LLM | Ollama on the host | Groq free, OpenRouter fallback |
| Cache | Redis container | Redis Cloud free |
| Registry | Postgres container | Neon free |
| Tracing | Langfuse Cloud, or self-hosted via the `langfuse` compose profile | Langfuse Cloud |
| Speech-to-text | Sarvam (no STT model runs in-process) | Sarvam |

`local` is the benchmark rig: nothing crosses the internet on the retrieval path, which is
what makes the sub-200ms measurement meaningful. `cloud` is the live demo that fits free
tiers. Both are benchmarked and both sets of numbers are published - see
[latency.md](latency.md) for why conflating them would be dishonest.

The `local` profile is English-only on the embedding side, because `bge-base-en-v1.5` is an
English model. Querying the Indic corpus therefore requires the `cloud` profile or a
multilingual local model.

## Free tiers, and what each one costs you

**Qdrant Cloud** - 1 GB, roughly 250K vectors at 768d, permanent. Keeps named sparse vectors,
so hybrid retrieval and RRF are unchanged from self-hosted. Only the URL and API key differ.

**Jina AI** - 10M tokens shared across embedding and reranking on one key. `jina-embeddings-v3`
is multilingual at 1024d and covers all five Indic languages. Changing embedding provider
changes the embedding fingerprint and therefore requires a re-index; this is enforced at
startup rather than discovered later through bad results.

**Sarvam Saaras v3** - authenticates with an `api-subscription-key` header, not a bearer
token, which is the usual first thing to get wrong. See [voice.md](voice.md).

**Groq** - OpenAI-compatible, so [`adapters/generation.py`](../src/fastrag/adapters/generation.py)
needs no changes. The free tier allows 30 requests per minute, which is the single most
likely thing to break a demo; the harness retries 429s with jittered backoff and honours
`Retry-After`, and a fallback provider takes over when retries are exhausted.

**Neon** - 0.5 GB Postgres, permanent. Render's own free Postgres deletes itself after 30
days, so it is not used for the registry.

**Redis Cloud** - 30 MB including the RediSearch module, which the semantic cache needs for
`FT.CREATE`. Upstash Redis does not support it; set `FASTRAG_SEMANTIC_CACHE_ENABLED=false`
there and exact caching still works. The code also degrades to exact-only automatically if
the module turns out to be missing at runtime, rather than failing the request.

**Langfuse Cloud** - 50K units/month. Tracing is fail-open throughout, so an outage or a
missing key costs observability and nothing else.

## Fingerprinting hosted models

Local artifacts are pinned by SHA256 of the ONNX file. Hosted models have no local file to
checksum, so the fingerprint component becomes `provider:model` and the revision becomes
`hosted-api` (`Settings.active_dense_artifact`). This is a weaker guarantee, and honestly so:
a provider can change a model behind a stable name without telling you. The mitigation is the
golden gate - a silent model change shows up as a quality regression rather than passing
unnoticed.

`verify_configured_models` skips checksum verification when the active provider is hosted,
so the cloud profile starts without local model files present.

## The fallback chain is never silent

When the primary generator exhausts its retries, `FallbackGenerator` switches to the
secondary and records it: the `generator_provider` field in the response says which provider
actually answered, a `FALLBACKS` counter increments, and the switch is traced. This preserves
the rule from [llm-providers.md](llm-providers.md) that a degraded answer must be
distinguishable from a normal one.

Configure it with `FASTRAG_LLM_FALLBACK_BASE_URL`, `_API_KEY`, and `_MODEL`. Leave them unset
and there is no fallback; the request fails loudly instead.
