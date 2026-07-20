from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from ..domain import Chunk


class GeneratorError(RuntimeError):
    pass


class OpenAICompatibleGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        max_tokens: int,
        timeout_seconds: float,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._headers = {"Authorization": f"Bearer {api_key}"}
        self._model = model
        self._system_prompt = system_prompt
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self.last_usage: dict[str, int] = {}

    async def stream(self, query: str, contexts: Sequence[Chunk]) -> AsyncIterator[str]:
        context = "\n\n".join(
            f'<source id="{chunk.chunk_id}">\n{chunk.text}\n</source>' for chunk in contexts
        )
        payload = {
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
        timeout = httpx.Timeout(self._timeout, connect=min(5.0, self._timeout))
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST", self._url, headers=self._headers, json=payload
            ) as response:
                if response.status_code >= 400:
                    body = (await response.aread())[:1_000].decode(errors="replace")
                    raise GeneratorError(f"generator returned {response.status_code}: {body}")
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
