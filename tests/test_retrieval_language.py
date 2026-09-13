"""The language filter can widen to a corpus's source language."""

from __future__ import annotations

import pytest

from fastrag.adapters.retrieval import QdrantHybridRetriever


class _RecordingClient:
    def __init__(self) -> None:
        self.filters: list[object] = []

    def query_points(self, **kwargs: object):
        self.filters.append(kwargs["query_filter"])

        class _Response:
            points: list[object] = []

        return _Response()

    def create_payload_index(self, **_: object) -> None:
        return None


def _retriever(client: object, fallback: tuple[str, ...] = ()) -> QdrantHybridRetriever:
    retriever = QdrantHybridRetriever.__new__(QdrantHybridRetriever)
    retriever._client = client  # type: ignore[attr-defined]
    retriever._collection = "kb"  # type: ignore[attr-defined]
    retriever._collection_provider = None  # type: ignore[attr-defined]
    retriever._leg_k = 40  # type: ignore[attr-defined]
    retriever._sparse = None  # type: ignore[attr-defined]
    retriever._fallback_languages = fallback  # type: ignore[attr-defined]
    return retriever


def _language_match(query_filter: object) -> object:
    (condition,) = [c for c in query_filter.must if c.key == "language"]  # type: ignore[attr-defined]
    return condition.match


@pytest.mark.asyncio
async def test_language_filter_is_exact_by_default() -> None:
    """A translated corpus keeps today's behaviour: Hindi queries see Hindi chunks."""
    client = _RecordingClient()
    await _retriever(client).retrieve("q", [1.0], 5, language="hi")
    assert _language_match(client.filters[0]).value == "hi"


@pytest.mark.asyncio
async def test_language_filter_widens_to_fallback_languages() -> None:
    """A cross-lingual corpus indexed in English must stay searchable in Hindi."""
    client = _RecordingClient()
    await _retriever(client, ("en",)).retrieve("q", [1.0], 5, language="hi")
    assert sorted(_language_match(client.filters[0]).any) == ["en", "hi"]


@pytest.mark.asyncio
async def test_fallback_does_not_duplicate_the_requested_language() -> None:
    client = _RecordingClient()
    await _retriever(client, ("en",)).retrieve("q", [1.0], 5, language="en")
    assert _language_match(client.filters[0]).value == "en"


@pytest.mark.asyncio
async def test_no_language_means_no_language_condition() -> None:
    client = _RecordingClient()
    await _retriever(client, ("en",)).retrieve("q", [1.0], 5)
    query_filter = client.filters[0]
    assert all(c.key != "language" for c in query_filter.must)  # type: ignore[attr-defined]


def test_fallback_languages_setting_is_normalised() -> None:
    from fastrag.config import Settings

    settings = Settings(retrieval_fallback_languages=" en-IN, ,EN ")
    assert settings.retrieval_fallback_language_list == ["en", "en"]
    assert Settings(retrieval_fallback_languages="").retrieval_fallback_language_list == []
