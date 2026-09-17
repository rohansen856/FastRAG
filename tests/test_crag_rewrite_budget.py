"""The CRAG rewrite leaves a reasoning model room to answer in Indic scripts."""

from __future__ import annotations

import pytest

from fastrag.crag import REWRITE_MAX_TOKENS, CorrectiveRetrieval


class _RecordingGenerator:
    def __init__(self) -> None:
        self.max_tokens: object = None

    async def complete_json(self, **kwargs: object) -> dict[str, object]:
        self.max_tokens = kwargs["max_tokens"]
        return {"rewritten_query": "rewritten"}


@pytest.mark.asyncio
async def test_rewrite_budget_covers_reasoning_and_indic_output() -> None:
    """At 200 tokens gpt-oss-20b spent the budget reasoning over a Tamil query and
    returned no JSON at all; 800 succeeded for English, Hindi and Tamil."""
    generator = _RecordingGenerator()
    crag = CorrectiveRetrieval.__new__(CorrectiveRetrieval)
    crag._generator = generator  # type: ignore[attr-defined]
    assert await crag._rewrite("API-ஐ Render-இல் எப்படி டிப்ளாய் செய்வது?", deadline=None) == "rewritten"
    assert generator.max_tokens == REWRITE_MAX_TOKENS >= 800
