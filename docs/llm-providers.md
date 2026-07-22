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
