from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from ..chunking import context_of
from ..domain import Chunk
from ..harness import (
    Deadline,
    ProviderError,
    ProviderHarness,
    classify,
    retry_after_seconds,
)
from ..metrics import FALLBACKS, RETRIES


class GeneratorError(RuntimeError):
    pass


class OpenAICompatibleGenerator:
    """Streaming Chat Completions client for any OpenAI-compatible provider."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        max_tokens: int,
        timeout_seconds: float,
        harness: ProviderHarness | None = None,
        provider_name: str = "generator",
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._harness = harness or ProviderHarness(provider_name)
        self.provider_name = provider_name
        self.model = model
        self.last_usage: dict[str, int] = {}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds)),
            headers={"Authorization": f"Bearer {api_key}"},
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )

    def _payload(self, query: str, contexts: Sequence[Chunk]) -> dict[str, Any]:
        # `context_of` widens sentence-window and hierarchical chunks to the span
        # they were indexed to stand in for.
        context = "\n\n".join(
            f'<source id="{chunk.chunk_id}">\n{context_of(chunk)}\n</source>' for chunk in contexts
        )
        return {
            "model": self._model,
            "temperature": 0,
            "max_tokens": self._max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [
                {"role": "system", "content": self._system_prompt},
                {
                    "role": "user",
                    "content": f"Question:\n{query}\n\nSources:\n{context}",
                },
            ],
        }

    async def stream(
        self,
        query: str,
        contexts: Sequence[Chunk],
        *,
        deadline: Deadline | None = None,
    ) -> AsyncIterator[str]:
        payload = self._payload(query, contexts)
        policy = self._harness.policy
        breaker = self._harness.breaker
        breaker.before()
        for attempt in range(policy.max_attempts):
            if deadline is not None:
                deadline.check(self.provider_name, "generation")
            emitted = False
            try:
                async for token in self._stream_once(payload):
                    emitted = True
                    yield token
            except Exception as exc:  # noqa: BLE001 - normalised by classify()
                error = classify(self.provider_name, exc)
                # Never retry once tokens have reached the caller; a second
                # attempt would duplicate the answer mid-sentence.
                if emitted or not error.retryable or attempt == policy.max_attempts - 1:
                    breaker.record_failure()
                    raise error from exc
                reason = str(error.status_code) if error.status_code else "transport"
                RETRIES.labels(provider=self.provider_name, reason=reason).inc()
                delay = retry_after_seconds(exc) or policy.backoff(attempt)
                if deadline is not None and delay >= deadline.remaining:
                    breaker.record_failure()
                    raise error from exc
                await asyncio.sleep(delay)
            else:
                breaker.record_success()
                return

    async def _stream_once(self, payload: dict[str, Any]) -> AsyncIterator[str]:
        async with self._client.stream("POST", self._url, json=payload) as response:
            if response.status_code >= 400:
                body = (await response.aread())[:1_000].decode(errors="replace")
                raise httpx.HTTPStatusError(
                    f"generator returned {response.status_code}: {body}",
                    request=response.request,
                    response=response,
                )
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    return
                try:
                    event = json.loads(data)
                    if event.get("usage"):
                        self.last_usage = {
                            str(key): int(value) for key, value in event["usage"].items()
                        }
                    choices = event.get("choices") or []
                    content = choices[0]["delta"].get("content") if choices else None
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise GeneratorError("invalid streaming event from generator") from exc
                if content:
                    yield str(content)

    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str = "result",
        max_tokens: int = 256,
        deadline: Deadline | None = None,
    ) -> dict[str, Any]:
        """Structured, schema-constrained completion used by CRAG and guardrails."""
        payload = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

        async def call() -> dict[str, Any]:
            response = await self._client.post(self._url, json=payload)
            response.raise_for_status()
            body = response.json()
            content = body["choices"][0]["message"]["content"]
            parsed: dict[str, Any] = json.loads(content)
            return parsed

        return await self._harness.call(call, stage="structured", deadline=deadline)

    async def aclose(self) -> None:
        await self._client.aclose()


class FallbackGenerator:
    """Primary generator with an explicit, observable secondary.

    The fallback is never silent: the provider actually used is exposed on
    `last_provider`, counted in Prometheus, and surfaced in the query response.
    """

    def __init__(
        self, primary: OpenAICompatibleGenerator, secondary: OpenAICompatibleGenerator
    ) -> None:
        self._primary = primary
        self._secondary = secondary
        self.last_provider = primary.provider_name
        self.last_usage: dict[str, int] = {}

    @property
    def model(self) -> str:
        return self._primary.model

    async def stream(
        self,
        query: str,
        contexts: Sequence[Chunk],
        *,
        deadline: Deadline | None = None,
    ) -> AsyncIterator[str]:
        emitted = False
        try:
            async for token in self._primary.stream(query, contexts, deadline=deadline):
                emitted = True
                self.last_provider = self._primary.provider_name
                yield token
        except ProviderError as exc:
            if emitted:
                raise
            FALLBACKS.labels(reason=str(exc.status_code or "error")).inc()
            self.last_provider = self._secondary.provider_name
            async for token in self._secondary.stream(query, contexts, deadline=deadline):
                yield token
            self.last_usage = self._secondary.last_usage
            return
        self.last_usage = self._primary.last_usage

    async def complete_json(self, **kwargs: Any) -> dict[str, Any]:
        try:
            return await self._primary.complete_json(**kwargs)
        except ProviderError as exc:
            FALLBACKS.labels(reason=str(exc.status_code or "error")).inc()
            return await self._secondary.complete_json(**kwargs)

    async def aclose(self) -> None:
        await self._primary.aclose()
        await self._secondary.aclose()
