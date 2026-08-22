from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest

from fastrag.calibration import Calibration
from fastrag.crag import CorrectiveRetrieval
from fastrag.domain import CachedAnswer, Chunk, Citation, RankedChunk
from fastrag.guardrails import Guardrails
from fastrag.pipeline import PipelineConfig, QueryPipeline


class FakeEmbedder:
    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector or [1.0, 0.0]

    async def embed_query(self, query: str, *, deadline: object = None) -> list[float]:
        return list(self.vector)

    async def embed_documents(
        self, documents: Sequence[str], *, deadline: object = None
    ) -> list[list[float]]:
        return [list(self.vector) for _ in documents]


class FakeRetriever:
    def __init__(self, chunks: list[Chunk]) -> None:
        self.chunks = chunks
        self.calls: list[dict[str, object]] = []

    async def retrieve(
        self,
        query: str,
        vector: list[float],
        limit: int,
        *,
        collection: str | None = None,
        strategy: str | None = None,
        language: str | None = None,
        document_ids: list[str] | None = None,
        deadline: object = None,
    ) -> list[Chunk]:
        self.calls.append(
            {
                "query": query,
                "strategy": strategy,
                "language": language,
                "document_ids": document_ids,
            }
        )
        if document_ids is not None:
            allowed = set(document_ids)
            filtered = [chunk for chunk in self.chunks if chunk.document_id in allowed]
            return filtered[:limit]
        return [
            chunk
            for chunk in self.chunks
            if not chunk.metadata.get("session_upload")
        ][:limit]


class FakeReranker:
    def __init__(self, score: float = 0.9, *, strip_scores: dict[str, float] | None = None) -> None:
        self.score = score
        self.strip_scores = strip_scores or {}

    async def rerank(
        self,
        query: str,
        candidates: Sequence[Chunk],
        limit: int,
        *,
        deadline: object = None,
    ) -> list[RankedChunk]:
        return [RankedChunk(chunk=chunk, score=self.score) for chunk in candidates[:limit]]

    async def score(
        self, query: str, texts: Sequence[str], *, deadline: object = None
    ) -> list[float]:
        return [self.strip_scores.get(text, self.score) for text in texts]


class FakeGenerator:
    def __init__(self, output: str, *, json_result: dict[str, object] | None = None) -> None:
        self.output = output
        self.json_result = json_result or {}
        self.last_provider = "fake"

    async def stream(
        self, query: str, contexts: Sequence[Chunk], *, deadline: object = None
    ) -> AsyncIterator[str]:
        for token in self.output.split(" "):
            yield token + " "

    async def complete_json(self, **kwargs: object) -> dict[str, object]:
        return dict(self.json_result)


class MemoryCache:
    def __init__(self) -> None:
        self.exact: CachedAnswer | None = None
        self.semantic: CachedAnswer | None = None
        self.writes: list[dict[str, object]] = []

    async def get_exact(self, namespace: str, query: str) -> CachedAnswer | None:
        return self.exact

    async def get_semantic(self, namespace: str, vector: list[float]) -> CachedAnswer | None:
        return self.semantic

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
        self.writes.append({"answer": answer, "semantic": semantic, "citations": citations})


@pytest.fixture
def chunk() -> Chunk:
    return Chunk(
        chunk_id="chunk-1",
        document_id="doc-1",
        text="Refunds are available for thirty days.",
        title="Refund policy",
        source_uri="policy.md",
        page=2,
    )


def make_pipeline(
    chunk: Chunk,
    *,
    output: str = "The refund period is thirty days [C:chunk-1].",
    score: float = 0.9,
    cache: MemoryCache | None = None,
    guardrails: Guardrails | None = None,
    crag: CorrectiveRetrieval | None = None,
    calibration: Calibration | None = None,
    max_context_tokens: int = 2400,
) -> tuple[QueryPipeline, MemoryCache]:
    answer_cache = cache or MemoryCache()
    resolved = calibration or Calibration(
        reranker_threshold=0.5,
        reranker_fingerprint="reranker",
        embedding_fingerprint="embedding",
        false_answer_rate=0.0,
        sample_count=30,
    )
    return (
        QueryPipeline(
            embedder=FakeEmbedder(),
            retriever=FakeRetriever([chunk]),
            reranker=FakeReranker(score),
            generator=FakeGenerator(output),
            cache=answer_cache,
            calibration=resolved,
            guardrails=guardrails,
            crag=crag,
            config=PipelineConfig(
                embedding_fingerprint="embedding",
                reranker_fingerprint="reranker",
                prompt_version="v1",
                generator_model="test-model",
                max_answer_tokens=200,
                content_version="test-index",
                max_context_tokens=max_context_tokens,
            ),
        ),
        answer_cache,
    )
