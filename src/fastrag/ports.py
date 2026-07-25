from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from .domain import CachedAnswer, Chunk, Citation, RankedChunk, Transcript
from .harness import Deadline


class Embedder(Protocol):
    async def embed_query(self, query: str, *, deadline: Deadline | None = None) -> list[float]: ...

    async def embed_documents(
        self, documents: Sequence[str], *, deadline: Deadline | None = None
    ) -> list[list[float]]: ...


class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        vector: list[float],
        limit: int,
        *,
        collection: str | None = None,
        strategy: str | None = None,
        language: str | None = None,
        deadline: Deadline | None = None,
    ) -> list[Chunk]: ...


class Reranker(Protocol):
    async def rerank(
        self,
        query: str,
        candidates: Sequence[Chunk],
        limit: int,
        *,
        deadline: Deadline | None = None,
    ) -> list[RankedChunk]: ...


class AnswerGenerator(Protocol):
    def stream(
        self,
        query: str,
        contexts: Sequence[Chunk],
        *,
        deadline: Deadline | None = None,
    ) -> AsyncIterator[str]: ...


class StructuredGenerator(Protocol):
    async def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str = "result",
        max_tokens: int = 256,
        deadline: Deadline | None = None,
    ) -> dict[str, Any]: ...


class Transcriber(Protocol):
    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "audio.wav",
        language: str | None = None,
        deadline: Deadline | None = None,
    ) -> Transcript: ...


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
