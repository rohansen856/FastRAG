# LLM providers

FastRAG talks to one generation interface: an OpenAI-compatible streaming Chat Completions
endpoint at:

```text
{FASTRAG_LLM_BASE_URL}/chat/completions
```

The configured model must support streaming responses with delta content. If the provider
also emits final usage in `stream_options.include_usage`, FastRAG records it in Langfuse.
Providers that do not support OpenAI-compatible Chat Completions should be placed behind a
gateway such as LiteLLM, OpenRouter, a custom adapter, or a small internal proxy.

## Required environment

```bash
FASTRAG_LLM_BASE_URL=<base-url-without-/chat/completions>
FASTRAG_LLM_API_KEY=<provider-token>
FASTRAG_LLM_MODEL=<provider-model-name>
FASTRAG_MAX_ANSWER_TOKENS=200
FASTRAG_LLM_TIMEOUT_SECONDS=20
```

Changing `FASTRAG_LLM_MODEL`, prompt version, or answer token limit creates a new cache
namespace. Do not silently switch fallback models under the same release.

## Ollama

Ollama exposes an OpenAI-compatible local API at `/v1`.

Host development:

```bash
ollama pull llama3.2
curl -fsS http://127.0.0.1:11434/v1/models
```

FastRAG running in Docker Compose:

```bash
FASTRAG_LLM_BASE_URL=http://host.docker.internal:11434/v1
FASTRAG_LLM_API_KEY=ollama
FASTRAG_LLM_MODEL=llama3.2:latest
```

FastRAG running directly on the host:

```bash
FASTRAG_LLM_BASE_URL=http://127.0.0.1:11434/v1
FASTRAG_LLM_API_KEY=ollama
FASTRAG_LLM_MODEL=llama3.2:latest
```

Ollama is good for local functional tests and private deployments. Measure TTFT and citation
compliance before using a small local model for production traffic; context-only citation
formatting is stricter than ordinary chat.

## OpenAI

Use OpenAI's Chat Completions-compatible base URL:

```bash
FASTRAG_LLM_BASE_URL=https://api.openai.com/v1
FASTRAG_LLM_API_KEY=<openai-api-key>
FASTRAG_LLM_MODEL=<chat-completions-model>
```

Use a model that supports streamed chat completions. Keep the model string pinned in release
configuration and record any prompt changes through `FASTRAG_PROMPT_VERSION`.

## Anthropic

Anthropic's native Messages API is not the same wire format as OpenAI Chat Completions.
Use a gateway that presents Anthropic models through an OpenAI-compatible `/v1/chat/completions`
surface, then configure FastRAG against the gateway:

```bash
FASTRAG_LLM_BASE_URL=http://llm-gateway:4000/v1
FASTRAG_LLM_API_KEY=<gateway-key>
FASTRAG_LLM_MODEL=anthropic/<model-name>
```

Validate streaming chunks and usage accounting before enabling production traces, because
gateway behavior differs by provider and version.

## Gemini

Gemini's native API is also not FastRAG's direct wire format. Put it behind an
OpenAI-compatible gateway:

```bash
FASTRAG_LLM_BASE_URL=http://llm-gateway:4000/v1
FASTRAG_LLM_API_KEY=<gateway-key>
FASTRAG_LLM_MODEL=gemini/<model-name>
```

Run the golden evaluation after switching providers. Gemini model changes can alter citation
formatting and no-answer behavior even when retrieval is unchanged.

## Other OpenAI-compatible providers

Providers such as vLLM, LM Studio, OpenRouter, Together, Groq, Fireworks, and self-hosted
model gateways can work when they implement streaming Chat Completions closely enough:

```bash
FASTRAG_LLM_BASE_URL=<provider-or-gateway-/v1>
FASTRAG_LLM_API_KEY=<token>
FASTRAG_LLM_MODEL=<model>
```

Acceptance criteria for any provider:

- streams `choices[0].delta.content`;
- returns non-2xx errors with useful bodies;
- respects `temperature=0` and `max_tokens`;
- can follow the source-marker prompt reliably;
- keeps p95 TTFT under the service SLO at target concurrency;
- passes the golden evaluation thresholds with the production prompt.

### Reasoning models

`openai/gpt-oss-*` (the Groq default) reasons before it answers, and the reasoning tokens
count against `max_tokens`. On a self-corpus question about deploying to Render, the default
effort spent all 800 answer tokens reasoning and returned no content at all
(`finish_reason=length`); with `FASTRAG_LLM_REASONING_EFFORT=low` it used 63 characters of
reasoning and produced a full answer. The same starvation hit the 200-token CRAG rewrite for
a Tamil question. The setting is sent on both answers and structured completions, and only
when set - models without reasoning reject the field.

An empty or uncited generation is returned as `no_answer`, never as `answered`.

### Citation compliance

Every sentence must carry a `[C:chunk_id]` marker, and the validator fails closed. Models
drift from that on long, multi-step answers: they cite bare ids, or collect every marker at
the end. Prompt `v2` shows the per-sentence form by example; replaying the same retrieved
contexts through `openai/gpt-oss-20b`, it raised validated answers from 5 to 10 of 11 across
English, Hindi, Bengali, Telugu and Marathi, with no question lost. Long English how-to
answers remain the weakest case - count citation abstentions in the trace
(`abstention_reason`) before blaming retrieval.

### Answer language

The self-corpus is English, so every source a Hindi or Tamil question retrieves is English,
and without an instruction the model follows the sources. Prompt `v2` answered a Hindi CRAG
question, a Tamil and a Telugu question in English on every one of three runs each. Prompt
`v3` adds one line - answer in the question's language and script, keeping code and
identifiers as written - and answered all 18 runs across English, Hindi, Bengali, Tamil and
Telugu in the question's language, every one passing citation validation.

The semantic cache is keyed by that language as well (the request's `language`, or the
question's script when none is sent). Multilingual embeddings put a question and its
translation almost on top of each other, so without it a Hindi asker was served the cached
English answer.

## Provider change checklist

1. Set the new provider env vars in a separate release.
2. Run the Ollama/provider smoke script or an equivalent direct adapter smoke test.
3. Run `uv run pytest`.
4. Run the golden evaluation against a representative index.
5. Run the load test at expected QPS.
6. Compare Langfuse traces for answer length, citation failures, token use, cost, TTFT, and
   abstention rate.
7. Promote only after the new provider meets retrieval-independent generation quality and
   latency targets.

## Per-request LLM override (development)

When query overrides are enabled, a single query may pass `overrides.llm` with `base_url`,
`api_key`, `model`, and `max_tokens`. The server must already have a default LLM base URL
configured. API keys in traces are redacted. See [query-trace.md](query-trace.md).
