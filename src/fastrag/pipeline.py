from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .calibration import Calibration
from .chunking import context_of
from .citations import CitationValidationError, SentenceCitationBuffer
from .crag import CorrectiveRetrieval
from .documents import resolve_document_scope
from .domain import (
    ActiveIndex,
    CacheStatus,
    Chunk,
    CragTrace,
    GuardrailDecision,
    Outcome,
    QueryResponse,
    QueryTimings,
    RankedChunk,
    StageStatus,
    Transcript,
)
from .fingerprint import cache_namespace
from .guardrails import Guardrails, refusal_text
from .harness import Deadline
from .metrics import FAILURES, LATENCY, REQUESTS, STAGE_LATENCY, TTFT
from .observability import observation, trace_raw_content
from .ports import AnswerCache, AnswerGenerator, Embedder, Reranker, Retriever
from .query_trace import QueryTraceBuilder

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
    chunk_strategy: str = "sentence"
    deadline_seconds: float = 25.0
    profile: str = "local"


@dataclass(slots=True)
class _RequestState:
    """Per-request scratch space, kept off the pipeline so it stays reentrant."""

    query_id: str
    trace_id: str
    started: float
    timings: dict[str, float] = field(default_factory=dict)
    guardrail: GuardrailDecision | None = None
    crag: CragTrace | None = None
    transcript: Transcript | None = None
    trace: QueryTraceBuilder | None = None


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
        guardrails: Guardrails | None = None,
        crag: CorrectiveRetrieval | None = None,
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
        self._guardrails = guardrails or Guardrails(enabled=False)
        self._crag = crag
        from llama_index.core.utils import get_tokenizer

        self._tokenizer = get_tokenizer()

    async def run(
        self,
        query: str,
        *,
        trace_id: str | None = None,
        strategy: str | None = None,
        language: str | None = None,
        document_id: str | None = None,
        document_ids: list[str] | None = None,
        transcript: Transcript | None = None,
    ) -> QueryResponse:
        final: QueryResponse | None = None
        async for event in self.stream(
            query,
            trace_id=trace_id,
            strategy=strategy,
            language=language,
            document_id=document_id,
            document_ids=document_ids,
            transcript=transcript,
        ):
            if event["event"] == "final":
                final = QueryResponse.model_validate(event["data"])
        if final is None:
            raise PipelineUnavailable("pipeline", "query completed without a final result")
        return final

    async def stream(
        self,
        query: str,
        *,
        trace_id: str | None = None,
        strategy: str | None = None,
        language: str | None = None,
        document_id: str | None = None,
        document_ids: list[str] | None = None,
        transcript: Transcript | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        state = _RequestState(
            query_id=uuid.uuid4().hex,
            trace_id=trace_id or uuid.uuid4().hex,
            started=time.perf_counter(),
            transcript=transcript,
        )
        state.trace = QueryTraceBuilder(
            query=query,
            strategy=strategy or self._config.chunk_strategy,
            language=language,
            document_ids=scoped_documents if (scoped_documents := resolve_document_scope(
                document_id=document_id, document_ids=document_ids
            )) else [],
            profile=self._config.profile,
            embedding_fingerprint=self._config.embedding_fingerprint,
            reranker_fingerprint=self._config.reranker_fingerprint,
            generator_model=self._config.generator_model,
            candidate_k=self._config.candidate_k,
            context_top_k=self._config.context_top_k,
            reranker_threshold=self._calibration.reranker_threshold,
            crag_confident_threshold=self._calibration.crag_confident_threshold,
            offtopic_threshold=self._calibration.offtopic_threshold,
        )
        if transcript is not None:
            state.timings["stt"] = transcript.duration_ms / 1000
            state.trace.set_transcript(transcript)
        deadline = Deadline(self._config.deadline_seconds)
        active_strategy = strategy or self._config.chunk_strategy
        document_scope = ",".join(scoped_documents) if scoped_documents else None

        yield {
            "event": "meta",
            "data": {"query_id": state.query_id, "trace_id": state.trace_id},
        }

        guard_started = time.perf_counter()
        decision = self._guardrails.check_text(query)
        state.timings["guardrail"] = time.perf_counter() - guard_started
        if state.trace is not None:
            if decision.allowed:
                detail = None
            elif decision.rule:
                detail = decision.rule.value
            else:
                detail = "blocked"
            state.trace.record_stage(
                "guardrail",
                status=StageStatus.OK if decision.allowed else StageStatus.BLOCKED,
                duration_ms=state.timings["guardrail"] * 1000,
                detail=detail,
            )
        if not decision.allowed:
            async for event in self._refuse(state, decision):
                yield event
            return

        try:
            active_index = (
                await self._index_provider()
                if self._index_provider is not None
                else ActiveIndex(content_version=self._config.content_version, collection_name="")
            )
        except Exception as exc:
            FAILURES.labels(stage="index_registry").inc()
            raise PipelineUnavailable("index_registry", str(exc)) from exc

        if state.trace is not None:
            state.trace.set_index(
                collection_name=active_index.collection_name,
                content_version=active_index.content_version,
            )

        namespace = cache_namespace(
            content_version=active_index.content_version,
            embedding_fingerprint=self._config.embedding_fingerprint,
            prompt_version=self._config.prompt_version,
            generator_model=self._config.generator_model,
            max_answer_tokens=self._config.max_answer_tokens,
            chunk_strategy=active_strategy,
            document_scope=document_scope,
        )
        if state.trace is not None:
            state.trace.set_cache_namespace(namespace)

        cache_started = time.perf_counter()
        cached = await self._cache_read("exact_cache", self._cache.get_exact(namespace, query))
        if state.trace is not None:
            state.trace.record_stage(
                "exact_cache",
                status=StageStatus.OK,
                duration_ms=(time.perf_counter() - cache_started) * 1000,
                detail="exact hit" if cached is not None else "miss",
            )
        if cached is not None:
            if state.trace is not None:
                state.trace.mark_cache_hit(CacheStatus.EXACT)
            async for event in self._from_cache(state, cached, active_index.content_version):
                yield event
            return

        vector = await self._required(
            "embedding", self._embedder.embed_query(query, deadline=deadline), state.timings, state
        )

        if scoped_documents is None:
            vector_started = time.perf_counter()
            vector_decision = self._guardrails.check_vector(vector)
            vector_elapsed = time.perf_counter() - vector_started
            if state.trace is not None:
                detail = None
                if not vector_decision.allowed:
                    detail = (
                        vector_decision.rule.value if vector_decision.rule else "blocked"
                    )
                state.trace.record_stage(
                    "vector_guardrail",
                    status=StageStatus.OK
                    if vector_decision.allowed
                    else StageStatus.BLOCKED,
                    duration_ms=vector_elapsed * 1000,
                    detail=detail,
                )
            if not vector_decision.allowed:
                async for event in self._refuse(state, vector_decision):
                    yield event
                return
        elif state.trace is not None:
            state.trace.record_stage(
                "vector_guardrail",
                status=StageStatus.SKIPPED,
                detail="document scope",
            )

        semantic_started = time.perf_counter()
        cached = await self._cache_read(
            "semantic_cache", self._cache.get_semantic(namespace, vector)
        )
        if state.trace is not None:
            state.trace.record_stage(
                "semantic_cache",
                status=StageStatus.OK,
                duration_ms=(time.perf_counter() - semantic_started) * 1000,
                detail="semantic hit" if cached is not None else "miss",
            )
        if cached is not None:
            if state.trace is not None:
                state.trace.mark_cache_hit(CacheStatus.SEMANTIC)
            async for event in self._from_cache(state, cached, active_index.content_version):
                yield event
            return

        collection = active_index.collection_name or None
        candidates = await self._required(
            "retrieval",
            self._retriever.retrieve(
                query,
                vector,
                self._config.candidate_k,
                collection=collection,
                strategy=active_strategy,
                language=language,
                document_ids=scoped_documents,
                deadline=deadline,
            ),
            state.timings,
            state,
        )
        if state.trace is not None:
            state.trace.set_retrieved(candidates)
        if not candidates:
            if state.trace is not None:
                state.trace.abstention_reason = "No chunks retrieved"
                state.trace.mark_abstention_short_circuit("retrieval")
            async for event in self._no_answer(
                state, namespace, query, vector, active_index.content_version
            ):
                yield event
            return

        ranked = await self._required(
            "rerank",
            self._reranker.rerank(query, candidates, self._config.candidate_k, deadline=deadline),
            state.timings,
            state,
        )
        if state.trace is not None:
            state.trace.set_reranked(ranked)

        ranked, abstain = await self._correct(
            query,
            ranked,
            state,
            collection=collection,
            strategy=active_strategy,
            language=language,
            document_ids=scoped_documents,
            deadline=deadline,
        )
        if scoped_documents and ranked:
            abstain = False
        if abstain:
            if state.trace is not None:
                top = ranked[0].score if ranked else None
                state.trace.abstention_reason = (
                    f"CRAG/rerank gate: top score {top:.3f} below threshold "
                    f"{self._calibration.reranker_threshold:.3f}"
                    if top is not None
                    else "CRAG/rerank gate: no ranked chunks"
                )
                state.trace.mark_abstention_short_circuit("crag")
            async for event in self._no_answer(
                state, namespace, query, vector, active_index.content_version
            ):
                yield event
            return

        contexts = self._select_contexts(ranked)
        if state.trace is not None:
            state.trace.set_contexts(contexts, ranked)
        if not contexts:
            if state.trace is not None:
                state.trace.abstention_reason = "No context selected within token budget"
                state.trace.mark_abstention_short_circuit("crag")
            async for event in self._no_answer(
                state, namespace, query, vector, active_index.content_version
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
                async for token in self._generator.stream(query, contexts, deadline=deadline):
                    raw_answer += token
                    for validated in citation_buffer.feed(token):
                        if first_chunk:
                            TTFT.observe(time.perf_counter() - state.started)
                            first_chunk = False
                        answer_chunks.append(validated)
                        yield self._chunk_event(validated)
                for validated in citation_buffer.finish():
                    if first_chunk:
                        TTFT.observe(time.perf_counter() - state.started)
                        first_chunk = False
                    answer_chunks.append(validated)
                    yield self._chunk_event(validated)
                generation_span.update(
                    model=self._config.generator_model,
                    usage_details=getattr(self._generator, "last_usage", None),
                    output=self._generation_trace_output(raw_answer),
                )
        except CitationValidationError as exc:
            if NO_ANSWER_TEXT.casefold() in raw_answer.casefold():
                async for event in self._no_answer(
                    state, namespace, query, vector, active_index.content_version
                ):
                    yield event
                return
            FAILURES.labels(stage="citation_validation").inc()
            raise PipelineUnavailable("citation_validation", str(exc)) from exc
        except Exception as exc:
            FAILURES.labels(stage="generation").inc()
            raise PipelineUnavailable("generation", str(exc)) from exc
        state.timings["generation"] = time.perf_counter() - generation_started
        STAGE_LATENCY.labels(stage="generation").observe(state.timings["generation"])
        if state.trace is not None:
            state.trace.record_timing_stage(
                "generation",
                state.timings["generation"],
                detail=self._config.generator_model,
            )
            state.trace.set_generator_provider(getattr(self._generator, "last_provider", None))
            state.trace.set_generation(self._generator)
            state.trace.set_cited_chunk_ids(
                [citation.chunk_id for citation in citation_buffer.citations()]
            )

        answer = " ".join(answer_chunks)
        citations = citation_buffer.citations()
        await self._cache_write(namespace, query, vector, answer, citations, semantic=True)
        final = self._response(
            state,
            Outcome.ANSWERED,
            answer,
            citations,
            CacheStatus.MISS,
            active_index.content_version,
        )
        self._record(final, state.started)
        yield {"event": "final", "data": final.model_dump(mode="json")}

    async def _correct(
        self,
        query: str,
        ranked: list[RankedChunk],
        state: _RequestState,
        *,
        collection: str | None,
        strategy: str | None,
        language: str | None,
        document_ids: list[str] | None,
        deadline: Deadline,
    ) -> tuple[list[RankedChunk], bool]:
        if self._crag is None:
            below = not ranked or ranked[0].score < self._calibration.reranker_threshold
            if document_ids and ranked:
                below = False
            if state.trace is not None:
                state.trace.record_stage(
                    "crag",
                    status=StageStatus.SKIPPED,
                    detail="CRAG disabled",
                )
            return ranked, below
        outcome = await self._crag.run(
            query,
            ranked,
            collection=collection,
            strategy=strategy,
            language=language,
            document_ids=document_ids,
            deadline=deadline,
            timings=state.timings,
        )
        state.crag = outcome.trace
        if "crag" in state.timings:
            STAGE_LATENCY.labels(stage="crag").observe(state.timings["crag"])
        if state.trace is not None:
            crag_detail = outcome.trace.action.value
            if outcome.trace.rewrites:
                crag_detail += f" · {outcome.trace.rewrites} rewrite(s)"
            state.trace.record_timing_stage(
                "crag",
                state.timings.get("crag", 0),
                detail=crag_detail,
            )
        return outcome.ranked, outcome.should_abstain

    async def _from_cache(
        self, state: _RequestState, cached: Any, content_version: str
    ) -> AsyncIterator[dict[str, Any]]:
        yield self._chunk_event(cached.answer)
        final = self._response(
            state,
            cached.outcome,
            cached.answer,
            list(cached.citations),
            cached.cache_status,
            content_version,
        )
        self._record(final, state.started)
        yield {"event": "final", "data": final.model_dump(mode="json")}

    async def _refuse(
        self, state: _RequestState, decision: GuardrailDecision
    ) -> AsyncIterator[dict[str, Any]]:
        """Guardrail refusals are never cached; they depend only on the input."""
        state.guardrail = decision
        rule = decision.rule
        text = refusal_text(rule) if rule is not None else "I can't answer that."
        yield self._chunk_event(text)
        final = self._response(
            state,
            Outcome.REFUSED,
            text,
            [],
            CacheStatus.MISS,
            self._config.content_version,
        )
        self._record(final, state.started)
        yield {"event": "final", "data": final.model_dump(mode="json")}

    async def _no_answer(
        self,
        state: _RequestState,
        namespace: str,
        query: str,
        vector: list[float],
        content_version: str,
    ) -> AsyncIterator[dict[str, Any]]:
        yield self._chunk_event(NO_ANSWER_TEXT)
        await self._cache_write(namespace, query, vector, NO_ANSWER_TEXT, [], semantic=False)
        final = self._response(
            state, Outcome.NO_ANSWER, NO_ANSWER_TEXT, [], CacheStatus.MISS, content_version
        )
        self._record(final, state.started)
        yield {"event": "final", "data": final.model_dump(mode="json")}

    async def _required(
        self,
        stage: str,
        operation: Any,
        timings: dict[str, float],
        state: _RequestState | None = None,
    ) -> Any:
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
        if state is not None and state.trace is not None:
            stage_id = "embedding" if stage == "embedding" else stage
            state.trace.record_timing_stage(stage_id, elapsed)
        return result

    @staticmethod
    def _generation_trace_output(raw_answer: str) -> dict[str, Any]:
        output: dict[str, Any] = {"answer_sha256": hashlib.sha256(raw_answer.encode()).hexdigest()}
        if trace_raw_content():
            output["answer"] = raw_answer
        return output

    @staticmethod
    def _ranking_trace_output(result: Any) -> list[dict[str, Any]]:
        include_text = trace_raw_content()
        output: list[dict[str, Any]] = []
        for item in result:
            chunk = getattr(item, "chunk", item)
            entry: dict[str, Any] = {
                "chunk_id": getattr(chunk, "chunk_id", "unknown"),
                "document_id": getattr(chunk, "document_id", "unknown"),
                "score": float(getattr(item, "score", getattr(chunk, "score", 0))),
            }
            if include_text:
                entry["text"] = getattr(chunk, "text", "")
            output.append(entry)
        return output

    def _select_contexts(self, ranked: list[RankedChunk]) -> list[Chunk]:
        contexts: list[Chunk] = []
        tokens_used = 0
        for item in ranked[: self._config.context_top_k]:
            # Budget against what the generator will actually read, which for
            # window and hierarchical chunks is wider than the indexed text.
            token_count = len(self._tokenizer(context_of(item.chunk)))
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
        state: _RequestState,
        outcome: Outcome,
        answer: str,
        citations: list[Any],
        cache_status: CacheStatus,
        content_version: str,
    ) -> QueryResponse:
        elapsed = time.perf_counter() - state.started
        timings = state.timings
        trace = None
        if state.trace is not None:
            trace = state.trace.build(cache_status=cache_status)
        return QueryResponse(
            query_id=state.query_id,
            trace_id=state.trace_id,
            outcome=outcome,
            answer=answer,
            citations=citations,
            cache_status=cache_status,
            index_version=content_version,
            guardrail=state.guardrail,
            crag=state.crag,
            transcript=state.transcript,
            generator_provider=getattr(self._generator, "last_provider", None),
            trace=trace,
            timings=QueryTimings(
                total_ms=elapsed * 1000,
                stt_ms=timings.get("stt", 0) * 1000,
                guardrail_ms=timings.get("guardrail", 0) * 1000,
                embedding_ms=timings.get("embedding", 0) * 1000,
                cache_ms=timings.get("cache", 0) * 1000,
                retrieval_ms=timings.get("retrieval", 0) * 1000,
                rerank_ms=timings.get("rerank", 0) * 1000,
                crag_ms=timings.get("crag", 0) * 1000,
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
