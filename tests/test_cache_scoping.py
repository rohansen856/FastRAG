"""Cached answers are only reused where they are still right to serve."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from conftest import make_pipeline

from fastrag.domain import CachedAnswer, CacheStatus, Citation, Outcome


class _NamespacedCache:
    """A cache that, like Redis, only returns entries written under the same namespace."""

    def __init__(self) -> None:
        self.entries: dict[str, CachedAnswer] = {}
        self.reads = 0

    async def get_exact(self, namespace: str, query: str) -> CachedAnswer | None:
        self.reads += 1
        return self.entries.get(namespace)

    async def get_semantic(self, namespace: str, vector: list[float]) -> CachedAnswer | None:
        self.reads += 1
        return self.entries.get(namespace)

    async def put(
        self,
        namespace: str,
        query: str,
        vector: list[float] | None,
        answer: str,
        citations: Sequence[Citation],
        *,
        semantic: bool,
    ) -> None:
        self.entries[namespace] = CachedAnswer(
            answer=answer, citations=tuple(citations), outcome=Outcome.ANSWERED,
            cache_status=CacheStatus.SEMANTIC,
        )


@pytest.mark.asyncio
async def test_a_hindi_question_never_reuses_an_english_answer(chunk):
    """Multilingual embeddings put a question and its translation side by side,
    so without a language in the key the Hindi asker is served the English answer."""
    cache = _NamespacedCache()
    pipeline, _ = make_pipeline(chunk, cache=cache)
    english = await pipeline.run("What is the refund period?")
    assert english.cache_status is CacheStatus.MISS
    hindi = await pipeline.run("रिफंड अवधि क्या है?")
    assert hindi.cache_status is CacheStatus.MISS
    repeat = await pipeline.run("रिफंड अवधि क्या है?", language="hi-IN")
    assert repeat.cache_status is not CacheStatus.MISS  # same language still hits


@pytest.mark.asyncio
async def test_document_scoped_answers_are_not_cached(chunk):
    """Deleting a document must take its answers with it; a cache entry would outlive it."""
    cache = _NamespacedCache()
    pipeline, _ = make_pipeline(chunk, cache=cache)
    await pipeline.run("What is the refund period?", document_id="doc-1")
    await pipeline.run("What is the refund period?", document_id="doc-1")
    assert cache.entries == {}
    assert cache.reads == 0
