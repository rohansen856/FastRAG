"""The vector store is retried once on a dropped connection, and no further."""

from __future__ import annotations

import pytest

from fastrag.adapters.retrieval import QdrantHybridRetriever


class _FlakyClient:
    """Fails the first N query_points calls, then succeeds."""

    def __init__(self, failures: int) -> None:
        self.failures = failures
        self.calls = 0

    def query_points(self, **_: object):
        self.calls += 1
        if self.calls <= self.failures:
            raise TimeoutError("read operation timed out")

        class _Response:
            points: list[object] = []

        return _Response()

    def create_payload_index(self, **_: object) -> None:
        return None


def _retriever(client: object) -> QdrantHybridRetriever:
    retriever = QdrantHybridRetriever.__new__(QdrantHybridRetriever)
    retriever._client = client  # type: ignore[attr-defined]
    retriever._collection = "kb"  # type: ignore[attr-defined]
    retriever._collection_provider = None  # type: ignore[attr-defined]
    retriever._leg_k = 40  # type: ignore[attr-defined]
    retriever._sparse = None  # type: ignore[attr-defined]
    return retriever


@pytest.mark.asyncio
async def test_retrieve_survives_one_dropped_connection() -> None:
    """A hosted cluster drops a connection often enough to lose a whole run."""
    client = _FlakyClient(failures=1)
    assert await _retriever(client).retrieve("q", [1.0, 0.0], 5) == []
    assert client.calls == 2


@pytest.mark.asyncio
async def test_retrieve_still_fails_closed_when_the_store_is_down() -> None:
    """The retry is bounded: a store that is genuinely down still raises."""
    client = _FlakyClient(failures=99)
    with pytest.raises(TimeoutError):
        await _retriever(client).retrieve("q", [1.0, 0.0], 5)
    assert client.calls == 2
