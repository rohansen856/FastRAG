from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from .domain import CachedAnswer, Chunk, Citation, RankedChunk


class Embedder(Protocol):
    async def embed_query(self, query: str) -> list[float]: ...

    async def embed_documents(self, documents: Sequence[str]) -> list[list[float]]: ...


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        vector: list[float],
        limit: int,
        *,
        collection: str | None = None,
    ) -> list[Chunk]: ...


class Reranker(Protocol):
    async def rerank(
        self, query: str, candidates: Sequence[Chunk], limit: int
    ) -> list[RankedChunk]: ...


class AnswerGenerator(Protocol):
    def stream(self, query: str, contexts: Sequence[Chunk]) -> AsyncIterator[str]: ...


class AnswerCache(Protocol):
    async def get_exact(self, namespace: str, query: str) -> CachedAnswer | None: ...

    async def get_semantic(self, namespace: str, vector: list[float]) -> CachedAnswer | None: ...

    async def put(
        self,
        namespace: str,
        query: str,
        vector: list[float] | None,
        answer: str,
        citations: Sequence[Citation],
        *,
        semantic: bool,
    ) -> None: ...


class IndexRegistry(Protocol):
    async def active_content_version(self) -> str: ...

    async def assert_embedding_fingerprint(self, fingerprint: str) -> None: ...
