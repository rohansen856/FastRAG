from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .calibration import Calibration
from .citations import CitationValidationError, SentenceCitationBuffer
from .domain import (
    ActiveIndex,
    CacheStatus,
    Chunk,
    Outcome,
    QueryResponse,
    QueryTimings,
    RankedChunk,
)
from .fingerprint import cache_namespace
from .metrics import FAILURES, LATENCY, REQUESTS, STAGE_LATENCY, TTFT
from .observability import observation
from .ports import AnswerCache, AnswerGenerator, Embedder, Reranker, Retriever

NO_ANSWER_TEXT = "I don't know based on the available sources."


class PipelineUnavailable(RuntimeError):
    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage


@dataclass(slots=True)
class PipelineConfig:
    embedding_fingerprint: str
    reranker_fingerprint: str
    prompt_version: str
    generator_model: str
    max_answer_tokens: int
    candidate_k: int = 20
    context_top_k: int = 5
    max_context_tokens: int = 2400
    content_version: str = "empty"


class QueryPipeline:
    def __init__(
        self,
        *,
        embedder: Embedder,
        retriever: Retriever,
        reranker: Reranker,
        generator: AnswerGenerator,
        cache: AnswerCache,
        calibration: Calibration,
        config: PipelineConfig,
        index_provider: Callable[[], Awaitable[ActiveIndex]] | None = None,
    ) -> None:
        calibration.validate(
            reranker_fingerprint=config.reranker_fingerprint,
            embedding_fingerprint=config.embedding_fingerprint,
        )
        self._embedder = embedder
        self._retriever = retriever
        self._reranker = reranker
        self._generator = generator
        self._cache = cache
        self._calibration = calibration
        self._config = config
        self._index_provider = index_provider
        from llama_index.core.utils import get_tokenizer

        self._tokenizer = get_tokenizer()

    async def run(self, query: str, *, trace_id: str | None = None) -> QueryResponse:
        final: QueryResponse | None = None
        async for event in self.stream(query, trace_id=trace_id):
            if event["event"] == "final":
                final = QueryResponse.model_validate(event["data"])
        if final is None:
            raise PipelineUnavailable("pipeline", "query completed without a final result")
        return final

    async def stream(
        self, query: str, *, trace_id: str | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        started = time.perf_counter()
        query_id = uuid.uuid4().hex
        trace_id = trace_id or uuid.uuid4().hex
        timings: dict[str, float] = {}
        try:
            active_index = (
                await self._index_provider()
                if self._index_provider is not None
                else ActiveIndex(
                    content_version=self._config.content_version,
                    collection_name="",
                )
            )
        except Exception as exc:
            FAILURES.labels(stage="index_registry").inc()
            raise PipelineUnavailable("index_registry", str(exc)) from exc
        namespace = cache_namespace(
            content_version=active_index.content_version,
            embedding_fingerprint=self._config.embedding_fingerprint,
            prompt_version=self._config.prompt_version,
            generator_model=self._config.generator_model,
            max_answer_tokens=self._config.max_answer_tokens,
        )
        yield {"event": "meta", "data": {"query_id": query_id, "trace_id": trace_id}}

        cached = await self._cache_read("exact_cache", self._cache.get_exact(namespace, query))
        if cached is not None:
            yield self._chunk_event(cached.answer)
            final = self._response(
                query_id,
                trace_id,
                cached.outcome,
                cached.answer,
                list(cached.citations),
                cached.cache_status,
                active_index.content_version,
                started,
                timings,
            )
            self._record(final, started)
            yield {"event": "final", "data": final.model_dump(mode="json")}
            return

        vector = await self._required("embedding", self._embedder.embed_query(query), timings)
        cached = await self._cache_read(
            "semantic_cache", self._cache.get_semantic(namespace, vector)
        )
        if cached is not None:
            yield self._chunk_event(cached.answer)
            final = self._response(
                query_id,
                trace_id,
                cached.outcome,
                cached.answer,
                list(cached.citations),
                cached.cache_status,
                active_index.content_version,
                started,
                timings,
            )
            self._record(final, started)
            yield {"event": "final", "data": final.model_dump(mode="json")}
            return

        candidates = await self._required(
            "retrieval",
            self._retriever.retrieve(
                query,
                vector,
                self._config.candidate_k,
                collection=active_index.collection_name or None,
            ),
            timings,
        )
        if not candidates:
            async for event in self._no_answer(
                namespace,
                query,
                vector,
                query_id,
                trace_id,
                active_index.content_version,
                started,
                timings,
            ):
                yield event
            return

        ranked = await self._required(
            "rerank",
            self._reranker.rerank(query, candidates, self._config.candidate_k),
            timings,
        )
        if not ranked or ranked[0].score < self._calibration.reranker_threshold:
            async for event in self._no_answer(
                namespace,
                query,
                vector,
                query_id,
                trace_id,
                active_index.content_version,
                started,
                timings,
            ):
                yield event
            return

        contexts = self._select_contexts(ranked)
        if not contexts:
            async for event in self._no_answer(
                namespace,
                query,
                vector,
                query_id,
                trace_id,
                active_index.content_version,
                started,
                timings,
            ):
                yield event
            return
        citation_buffer = SentenceCitationBuffer(contexts)
        answer_chunks: list[str] = []
        raw_answer = ""
        generation_started = time.perf_counter()
        first_chunk = True
        try:
            with observation(
                "generation",
                as_type="generation",
                metadata={"context_chunk_ids": [chunk.chunk_id for chunk in contexts]},
            ) as generation_span:
                async for token in self._generator.stream(query, contexts):
                    raw_answer += token
                    for validated in citation_buffer.feed(token):
                        if first_chunk:
                            TTFT.observe(time.perf_counter() - started)
                            first_chunk = False
                        answer_chunks.append(validated)
                        yield self._chunk_event(validated)
                for validated in citation_buffer.finish():
                    if first_chunk:
                        TTFT.observe(time.perf_counter() - started)
                        first_chunk = False
                    answer_chunks.append(validated)
                    yield self._chunk_event(validated)
                generation_span.update(
                    model=self._config.generator_model,
                    usage_details=getattr(self._generator, "last_usage", None),
                    output={"answer_sha256": hashlib.sha256(raw_answer.encode()).hexdigest()},
                )
        except CitationValidationError as exc:
            if raw_answer.strip() == NO_ANSWER_TEXT:
                async for event in self._no_answer(
                    namespace,
                    query,
                    vector,
                    query_id,
                    trace_id,
                    active_index.content_version,
                    started,
                    timings,
                ):
                    yield event
                return
            FAILURES.labels(stage="citation_validation").inc()
            raise PipelineUnavailable("citation_validation", str(exc)) from exc
        except Exception as exc:
            FAILURES.labels(stage="generation").inc()
            raise PipelineUnavailable("generation", str(exc)) from exc
        timings["generation"] = time.perf_counter() - generation_started
        STAGE_LATENCY.labels(stage="generation").observe(timings["generation"])

        answer = " ".join(answer_chunks)
        citations = citation_buffer.citations()
        await self._cache_write(namespace, query, vector, answer, citations, semantic=True)
        final = self._response(
            query_id,
            trace_id,
            Outcome.ANSWERED,
            answer,
            citations,
            CacheStatus.MISS,
            active_index.content_version,
            started,
            timings,
        )
        self._record(final, started)
        yield {"event": "final", "data": final.model_dump(mode="json")}

    async def _no_answer(
        self,
        namespace: str,
        query: str,
        vector: list[float],
        query_id: str,
        trace_id: str,
        content_version: str,
        started: float,
        timings: dict[str, float],
    ) -> AsyncIterator[dict[str, Any]]:
        yield self._chunk_event(NO_ANSWER_TEXT)
        await self._cache_write(namespace, query, vector, NO_ANSWER_TEXT, [], semantic=False)
        final = self._response(
            query_id,
            trace_id,
            Outcome.NO_ANSWER,
            NO_ANSWER_TEXT,
            [],
            CacheStatus.MISS,
            content_version,
            started,
            timings,
        )
        self._record(final, started)
        yield {"event": "final", "data": final.model_dump(mode="json")}

    async def _required(self, stage: str, operation: Any, timings: dict[str, float]) -> Any:
        started = time.perf_counter()
        try:
            with observation(stage) as span:
                result = await operation
                if stage in {"retrieval", "rerank"}:
                    span.update(output=self._ranking_trace_output(result))
        except Exception as exc:
            FAILURES.labels(stage=stage).inc()
            raise PipelineUnavailable(stage, str(exc)) from exc
        elapsed = time.perf_counter() - started
        timings[stage] = elapsed
        STAGE_LATENCY.labels(stage=stage).observe(elapsed)
        return result

    @staticmethod
    def _ranking_trace_output(result: Any) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for item in result:
            chunk = getattr(item, "chunk", item)
            output.append(
                {
                    "chunk_id": getattr(chunk, "chunk_id", "unknown"),
                    "document_id": getattr(chunk, "document_id", "unknown"),
                    "score": float(getattr(item, "score", getattr(chunk, "score", 0))),
                }
            )
        return output

    def _select_contexts(self, ranked: list[RankedChunk]) -> list[Chunk]:
        contexts: list[Chunk] = []
        tokens_used = 0
        for item in ranked[: self._config.context_top_k]:
            token_count = len(self._tokenizer(item.chunk.text))
            if tokens_used + token_count > self._config.max_context_tokens:
                continue
            contexts.append(item.chunk)
            tokens_used += token_count
        return contexts

    async def _cache_read(self, stage: str, operation: Any) -> Any:
        try:
            with observation(stage):
                return await operation
        except Exception:
            FAILURES.labels(stage=stage).inc()
            return None

    async def _cache_write(self, *args: Any, **kwargs: Any) -> None:
        try:
            with observation("cache_write"):
                await self._cache.put(*args, **kwargs)
        except Exception:
            FAILURES.labels(stage="cache_write").inc()

    def _response(
        self,
        query_id: str,
        trace_id: str,
        outcome: Outcome,
        answer: str,
        citations: list[Any],
        cache_status: CacheStatus,
        content_version: str,
        started: float,
        timings: dict[str, float],
    ) -> QueryResponse:
        elapsed = time.perf_counter() - started
        return QueryResponse(
            query_id=query_id,
            trace_id=trace_id,
            outcome=outcome,
            answer=answer,
            citations=citations,
            cache_status=cache_status,
            index_version=content_version,
            timings=QueryTimings(
                total_ms=elapsed * 1000,
                embedding_ms=timings.get("embedding", 0) * 1000,
                cache_ms=0,
                retrieval_ms=timings.get("retrieval", 0) * 1000,
                rerank_ms=timings.get("rerank", 0) * 1000,
                generation_ms=timings.get("generation", 0) * 1000,
            ),
        )

    @staticmethod
    def _chunk_event(text: str) -> dict[str, Any]:
        return {"event": "answer_chunk", "data": {"text": text}}

    @staticmethod
    def _record(response: QueryResponse, started: float) -> None:
        REQUESTS.labels(
            outcome=response.outcome.value, cache_status=response.cache_status.value
        ).inc()
        LATENCY.observe(time.perf_counter() - started)
