"""Reasoning effort is sent only when configured, on both kinds of completion."""

from __future__ import annotations

import pytest

from fastrag.adapters.generation import OpenAICompatibleGenerator


def _generator(effort: str | None) -> OpenAICompatibleGenerator:
    return OpenAICompatibleGenerator(
        base_url="http://unused",
        api_key="k",
        model="openai/gpt-oss-20b",
        system_prompt="s",
        max_tokens=10,
        timeout_seconds=1.0,
        reasoning_effort=effort,
    )


def test_streamed_answers_carry_the_configured_effort() -> None:
    assert _generator("low")._payload("q", [])["reasoning_effort"] == "low"
    # Models without reasoning reject the field, so it is absent unless configured.
    assert "reasoning_effort" not in _generator(None)._payload("q", [])


@pytest.mark.asyncio
async def test_structured_completions_carry_it_too() -> None:
    """The CRAG rewrite is where an unbounded reasoning pass first returned no JSON."""
    generator = _generator("low")
    sent: dict[str, object] = {}

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": '{"rewritten_query": "x"}'}}]}

    async def post(url: str, *, json: dict[str, object]) -> _Response:
        sent.update(json)
        return _Response()

    generator._client.post = post  # type: ignore[method-assign]
    await generator.complete_json(system="s", user="u", schema={"type": "object"})
    assert sent["reasoning_effort"] == "low"
