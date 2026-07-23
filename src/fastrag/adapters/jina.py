"""Jina AI embedding and reranking adapters.

One API key covers both endpoints, and the multilingual models cover every Indic
language in the corpus. The HTTP client is held open for the process lifetime:
a fresh TLS handshake per query costs more than the retrieval it wraps.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import httpx

from ..domain import Chunk, RankedChunk
from ..harness import Deadline, ProviderError, ProviderHarness

PROVIDER = "jina"


def _normalize(values: list[float]) -> list[float]:
    magnitude = sum(value * value for value in values) ** 0.5
    return values if magnitude == 0 else [value / magnitude for value in values]


class _JinaClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: float,
        harness: ProviderHarness | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds)),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
        self._harness = harness or ProviderHarness(PROVIDER)

    async def post(
        self, path: str, payload: dict[str, Any], *, stage: str, deadline: Deadline | None
    ) -> dict[str, Any]:
        async def call() -> dict[str, Any]:
            response = await self._client.post(f"{self._base_url}{path}", json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
            return body

        return await self._harness.call(call, stage=stage, deadline=deadline)

    async def aclose(self) -> None:
        await self._client.aclose()


class JinaEmbedder:
    """Dense embeddings via Jina's hosted multilingual models."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "jina-embeddings-v3",
        dimension: int = 1024,
        base_url: str = "https://api.jina.ai/v1",
        timeout_seconds: float = 15.0,
        normalize: bool = True,
        harness: ProviderHarness | None = None,
        client: _JinaClient | None = None,
    ) -> None:
        self._client = client or _JinaClient(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            harness=harness,
        )
        self._model = model
        self._dimension = dimension
        self._normalize = normalize

    async def embed_query(self, query: str, *, deadline: Deadline | None = None) -> list[float]:
        vectors = await self._embed([query], task="retrieval.query", deadline=deadline)
        return vectors[0]

    async def embed_documents(
        self, documents: Sequence[str], *, deadline: Deadline | None = None
    ) -> list[list[float]]:
        if not documents:
            return []
        return await self._embed(list(documents), task="retrieval.passage", deadline=deadline)

    async def _embed(
        self, inputs: list[str], *, task: str, deadline: Deadline | None
    ) -> list[list[float]]:
        body = await self._client.post(
            "/embeddings",
            {
                "model": self._model,
                "task": task,
                "dimensions": self._dimension,
                "input": inputs,
            },
            stage="embedding",
            deadline=deadline,
        )
        data = body.get("data")
        if not isinstance(data, list) or len(data) != len(inputs):
            raise ProviderError(PROVIDER, "embedding response did not match the input batch")
        # The API does not guarantee ordering, so re-sort on the returned index.
        ordered = sorted(data, key=lambda item: int(item.get("index", 0)))
        vectors = [[float(value) for value in item["embedding"]] for item in ordered]
        return [_normalize(vector) for vector in vectors] if self._normalize else vectors

    async def aclose(self) -> None:
        await self._client.aclose()


class JinaReranker:
    """Cross-encoder reranking via Jina's hosted multilingual reranker."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "jina-reranker-v2-base-multilingual",
        base_url: str = "https://api.jina.ai/v1",
        timeout_seconds: float = 15.0,
        harness: ProviderHarness | None = None,
        client: _JinaClient | None = None,
    ) -> None:
        self._client = client or _JinaClient(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            harness=harness,
        )
        self._model = model

    async def rerank(
        self,
        query: str,
        candidates: Sequence[Chunk],
        limit: int,
        *,
        deadline: Deadline | None = None,
    ) -> list[RankedChunk]:
        if not candidates:
            return []
        body = await self._client.post(
            "/rerank",
            {
                "model": self._model,
                "query": query,
                "documents": [chunk.text for chunk in candidates],
                "top_n": min(limit, len(candidates)),
            },
            stage="rerank",
            deadline=deadline,
        )
        results = body.get("results")
        if not isinstance(results, list):
            raise ProviderError(PROVIDER, "rerank response contained no results")
        ranked: list[RankedChunk] = []
        for item in results:
            index = int(item["index"])
            if not 0 <= index < len(candidates):
                raise ProviderError(PROVIDER, f"rerank returned out-of-range index {index}")
            ranked.append(
                RankedChunk(chunk=candidates[index], score=float(item["relevance_score"]))
            )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:limit]

    async def score(
        self, query: str, texts: Sequence[str], *, deadline: Deadline | None = None
    ) -> list[float]:
        """Raw relevance scores in input order, used by CRAG strip refinement."""
        if not texts:
            return []
        body = await self._client.post(
            "/rerank",
            {
                "model": self._model,
                "query": query,
                "documents": list(texts),
                "top_n": len(texts),
            },
            stage="rerank_strips",
            deadline=deadline,
        )
        scores = [0.0] * len(texts)
        for item in body.get("results", []):
            index = int(item["index"])
            if 0 <= index < len(texts):
                scores[index] = float(item["relevance_score"])
        return scores

    async def aclose(self) -> None:
        await self._client.aclose()


def build_jina_pair(
    *,
    api_key: str,
    base_url: str,
    embedding_model: str,
    embedding_dimension: int,
    reranker_model: str,
    timeout_seconds: float,
    harness: ProviderHarness | None = None,
) -> tuple[JinaEmbedder, JinaReranker]:
    """Share one HTTP client and circuit breaker across both Jina endpoints."""
    client = _JinaClient(
        base_url=base_url,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        harness=harness,
    )
    return (
        JinaEmbedder(
            api_key=api_key,
            model=embedding_model,
            dimension=embedding_dimension,
            client=client,
        ),
        JinaReranker(api_key=api_key, model=reranker_model, client=client),
    )
