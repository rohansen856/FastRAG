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

The `local` profile's default embedder, `bge-base-en-v1.5`, is an English model, so querying
in Hindi, Bengali, Tamil, Telugu or Marathi needs either Jina or the in-process multilingual
pair below.

## Multilingual without a hosted embedder

Both halves of retrieval can run in-process and still cover all six languages. This is how
the self-corpus is built, and it means neither indexing nor serving spends Jina balance:

```bash
FASTRAG_EMBEDDING_PROVIDER=fastembed
FASTRAG_RERANKER_PROVIDER=fastembed
FASTRAG_DENSE_MODEL_ID=intfloat/multilingual-e5-large
FASTRAG_DENSE_MODEL_REPOSITORY=qdrant/multilingual-e5-large-onnx
FASTRAG_DENSE_MODEL_REVISION=ac6781cd1cf88b8306a536d7c9d18a5bd57cc14b
FASTRAG_DENSE_MODEL_FILE=model.onnx_data
FASTRAG_DENSE_MODEL_SHA256=0cf1883fee81c63819a44e2ba0efa51d4043d9759685a4ebebbde97e0623d15c
FASTRAG_DENSE_DIMENSION=1024
FASTRAG_DENSE_QUERY_PREFIX="query: "
FASTRAG_DENSE_DOCUMENT_PREFIX="passage: "
FASTRAG_RERANKER_MODEL_ID=jinaai/jina-reranker-v2-base-multilingual
FASTRAG_RERANKER_MODEL_REPOSITORY=jinaai/jina-reranker-v2-base-multilingual
FASTRAG_RERANKER_REVISION=9cfeff2df7d40d1b78e75e5e9cebec92a99813c9
FASTRAG_RERANKER_MODEL_FILE=onnx/model.onnx
FASTRAG_RERANKER_SHA256=0ef3f7978f7bc52360864d74edc1a0e03d159af770a7767c4d5943496e616012
FASTRAG_RETRIEVAL_FALLBACK_LANGUAGES=en
```

The reranker is the same `jina-reranker-v2-base-multilingual` the hosted API serves, run
locally. The embedder is E5 rather than Jina's own `jina-embeddings-v3`, which FastEmbed can
also run: embedding the self-corpus with it on CPU peaked at 11.3 GB and was killed by the
kernel on a 15 GB machine.

Measured on the self-corpus's 437 English sections, with eight questions about FastRAG asked
in each language, E5 put the section that answers the question in the top 20 for 46 of 48
queries and at rank 1 for at least six of eight in every language. The two misses were
Tamil and Marathi phrasings of one guardrail question.

Details that matter:

- **E5 is asymmetric.** It is trained with `query: ` and `passage: ` markers, and FastEmbed
  adds neither, so both prefixes are configured. Prefixes are normalised to end in exactly one
  space, because they are part of the embedding fingerprint and hosting dashboards trim env
  values - `query:` arriving without its space would otherwise reject a valid index.
- **The corpus stays English.** A cross-lingual embedder matches a Hindi query to English
  chunks directly, but the `language` filter is an exact match on the chunk payload, and no
  chunk says `hi`. `FASTRAG_RETRIEVAL_FALLBACK_LANGUAGES=en` makes a `language=hi` query
  search `hi` and `en` chunks. Leave it empty for a corpus translated into every language,
  such as MSMARCO-XI, where exact filtering is the point.
- **Checksum the weights, not the graph.** E5's ONNX export keeps 2.2 GB of weights in
  `model.onnx_data` beside a 0.5 MB `model.onnx`. Production verifies the file named by
  `FASTRAG_DENSE_MODEL_FILE`, so it names the weights.
- **It costs memory and CPU.** Both models together peak at 3.7 GB resident. On 16 CPU
  cores, embedding a query takes 50-90 ms and reranking 20 candidates about 2.2 s, and
  reranking scales roughly with core count. That rules out Vercel functions and Render's
  free instance; see [deployment.md](deployment.md).
- **Licence.** `jina-reranker-v2-base-multilingual` is published under CC BY-NC 4.0. Running
  the weights yourself is non-commercial use only; the hosted Jina API is the licensed route
  for commercial deployments. E5 is MIT.

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
