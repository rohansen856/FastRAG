"""Build developer-facing query trace payloads for the pipeline."""

from __future__ import annotations

from typing import Any

from .domain import (
    CacheStatus,
    Chunk,
    ChunkTrace,
    GenerationTrace,
    PipelineStageTrace,
    QueryTrace,
    RankedChunk,
    StageStatus,
    Transcript,
)

EXCERPT_LEN = 320

STAGE_LABELS: dict[str, str] = {
    "stt": "Speech to text",
    "guardrail": "Text guardrails",
    "index_registry": "Index registry",
    "exact_cache": "Exact cache",
    "embedding": "Query embedding",
    "vector_guardrail": "Vector guardrail",
    "semantic_cache": "Semantic cache",
    "retrieval": "Hybrid retrieval",
    "rerank": "Cross-encoder rerank",
    "crag": "CRAG",
    "generation": "Answer generation",
}


def _excerpt(text: str) -> str:
    cleaned = text.strip()
    if len(cleaned) <= EXCERPT_LEN:
        return cleaned
    return cleaned[: EXCERPT_LEN - 1] + "…"


def chunk_traces_from_chunks(chunks: list[Chunk], *, start_rank: int = 1) -> list[ChunkTrace]:
    traces: list[ChunkTrace] = []
    for offset, chunk in enumerate(chunks):
        traces.append(
            ChunkTrace(
                rank=start_rank + offset,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                score=float(chunk.score),
                excerpt=_excerpt(chunk.text),
            )
        )
    return traces


def chunk_traces_from_ranked(ranked: list[RankedChunk], *, start_rank: int = 1) -> list[ChunkTrace]:
    traces: list[ChunkTrace] = []
    for offset, item in enumerate(ranked):
        chunk = item.chunk
        traces.append(
            ChunkTrace(
                rank=start_rank + offset,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                title=chunk.title,
                score=float(item.score),
                excerpt=_excerpt(chunk.text),
                refined=bool(chunk.metadata.get("refined")),
            )
        )
    return traces


class QueryTraceBuilder:
    def __init__(
        self,
        *,
        query: str,
        strategy: str,
        language: str | None,
        document_ids: list[str] | None,
        profile: str,
        embedding_fingerprint: str,
        reranker_fingerprint: str,
        generator_model: str,
        candidate_k: int,
        context_top_k: int,
        reranker_threshold: float,
        crag_confident_threshold: float | None,
        offtopic_threshold: float | None,
    ) -> None:
        self.query = query
        self.strategy = strategy
        self.language = language
        self.document_ids = list(document_ids or [])
        self.profile = profile
        self.embedding_fingerprint = embedding_fingerprint
        self.reranker_fingerprint = reranker_fingerprint
        self.generator_model = generator_model
        self.candidate_k = candidate_k
        self.context_top_k = context_top_k
        self.reranker_threshold = reranker_threshold
        self.crag_confident_threshold = crag_confident_threshold
        self.offtopic_threshold = offtopic_threshold
        self.collection_name: str | None = None
        self.content_version: str | None = None
        self.cache_namespace: str | None = None
        self.cache_status = CacheStatus.MISS
        self.stages: list[PipelineStageTrace] = []
        self.retrieved: list[ChunkTrace] = []
        self.reranked: list[ChunkTrace] = []
        self.contexts: list[ChunkTrace] = []
        self.cited_chunk_ids: list[str] = []
        self.abstention_reason: str | None = None
        self.generation: GenerationTrace | None = None
        self.stt_provider: str | None = None
        self.stt_model: str | None = None
        self.generator_provider: str | None = None

    def set_generator_provider(self, provider: str | None) -> None:
        self.generator_provider = provider

    def set_transcript(self, transcript: Transcript | None) -> None:
        if transcript is None:
            return
        self.stt_provider = transcript.provider
        self.stt_model = transcript.model
        self.record_stage(
            "stt",
            status=StageStatus.OK,
            duration_ms=transcript.duration_ms,
            detail=f"{transcript.provider} · {transcript.model}",
        )

    def set_index(self, *, collection_name: str, content_version: str) -> None:
        self.collection_name = collection_name or None
        self.content_version = content_version
        self.record_stage("index_registry", status=StageStatus.OK, duration_ms=0)

    def set_cache_namespace(self, namespace: str) -> None:
        self.cache_namespace = namespace

    def record_stage(
        self,
        stage_id: str,
        *,
        status: StageStatus,
        duration_ms: float = 0,
        detail: str | None = None,
    ) -> None:
        self.stages.append(
            PipelineStageTrace(
                id=stage_id,
                label=STAGE_LABELS.get(stage_id, stage_id),
                status=status,
                duration_ms=round(duration_ms, 2),
                detail=detail,
            )
        )

    def record_timing_stage(
        self, stage_id: str, seconds: float, *, detail: str | None = None
    ) -> None:
        self.record_stage(
            stage_id,
            status=StageStatus.OK,
            duration_ms=seconds * 1000,
            detail=detail,
        )

    def mark_cache_hit(self, status: CacheStatus) -> None:
        self.cache_status = status
        if status is CacheStatus.EXACT:
            for remaining in (
                "embedding",
                "vector_guardrail",
                "semantic_cache",
                "retrieval",
                "rerank",
                "crag",
                "generation",
            ):
                self.record_stage(
                    remaining, status=StageStatus.SKIPPED, detail="cache short-circuit"
                )
            return
        for remaining in ("retrieval", "rerank", "crag", "generation"):
            self.record_stage(remaining, status=StageStatus.SKIPPED, detail="cache short-circuit")

    def mark_abstention_short_circuit(self, from_stage: str) -> None:
        order = (
            "retrieval",
            "rerank",
            "crag",
            "generation",
        )
        if from_stage not in order:
            return
        for remaining in order[order.index(from_stage) + 1 :]:
            self.record_stage(remaining, status=StageStatus.SKIPPED, detail="abstained")

    def set_retrieved(self, chunks: list[Chunk]) -> None:
        self.retrieved = chunk_traces_from_chunks(chunks)

    def set_reranked(self, ranked: list[RankedChunk]) -> None:
        self.reranked = chunk_traces_from_ranked(ranked)

    def set_contexts(self, contexts: list[Chunk], ranked: list[RankedChunk]) -> None:
        score_by_id = {item.chunk.chunk_id: item.score for item in ranked}
        traces: list[ChunkTrace] = []
        for offset, chunk in enumerate(contexts):
            traces.append(
                ChunkTrace(
                    rank=offset + 1,
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    score=float(score_by_id.get(chunk.chunk_id, chunk.score)),
                    excerpt=_excerpt(chunk.text),
                    refined=bool(chunk.metadata.get("refined")),
                )
            )
        self.contexts = traces

    def set_cited_chunk_ids(self, chunk_ids: list[str]) -> None:
        self.cited_chunk_ids = chunk_ids

    def set_generation(self, generator: Any) -> None:
        usage = getattr(generator, "last_usage", None) or {}
        self.generation = GenerationTrace(
            provider=getattr(generator, "last_provider", None),
            model=self.generator_model,
            prompt_tokens=_usage_int(usage, "prompt_tokens"),
            completion_tokens=_usage_int(usage, "completion_tokens"),
            total_tokens=_usage_int(usage, "total_tokens"),
        )

    def build(self, *, cache_status: CacheStatus | None = None) -> QueryTrace:
        if cache_status is not None:
            self.cache_status = cache_status
        return QueryTrace(
            query=self.query,
            strategy=self.strategy,
            language=self.language,
            document_ids=self.document_ids,
            profile=self.profile,
            collection_name=self.collection_name,
            content_version=self.content_version,
            cache_namespace=self.cache_namespace,
            cache_status=self.cache_status,
            embedding_fingerprint=self.embedding_fingerprint,
            reranker_fingerprint=self.reranker_fingerprint,
            generator_model=self.generator_model,
            generator_provider=self.generator_provider,
            stt_provider=self.stt_provider,
            stt_model=self.stt_model,
            reranker_threshold=self.reranker_threshold,
            crag_confident_threshold=self.crag_confident_threshold,
            offtopic_threshold=self.offtopic_threshold,
            stages=self.stages,
            retrieved=self.retrieved,
            reranked=self.reranked,
            contexts=self.contexts,
            cited_chunk_ids=self.cited_chunk_ids,
            candidate_k=self.candidate_k,
            context_top_k=self.context_top_k,
            abstention_reason=self.abstention_reason,
            generation=self.generation,
        )


def _usage_int(usage: dict[str, Any], key: str) -> int | None:
    value = usage.get(key)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
