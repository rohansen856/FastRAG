from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    REFUSED = "refused"


class CacheStatus(StrEnum):
    MISS = "miss"
    EXACT = "exact"
    SEMANTIC = "semantic"


class CragAction(StrEnum):
    """Corrective-RAG verdict for the retrieved context."""

    CORRECT = "correct"
    AMBIGUOUS = "ambiguous"
    INCORRECT = "incorrect"
    DISABLED = "disabled"


class GuardrailRule(StrEnum):
    OFF_TOPIC = "off_topic"
    UNSAFE = "unsafe"
    PROMPT_INJECTION = "prompt_injection"
    UNSUPPORTED_LANGUAGE = "unsupported_language"
    EMPTY = "empty"


class LlmOverrides(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    max_tokens: int | None = Field(default=None, ge=1, le=8192)


class QueryOverrides(BaseModel):
    skip_cache: bool = False
    crag_enabled: bool | None = None
    candidate_k: int | None = Field(default=None, ge=1, le=100)
    context_top_k: int | None = Field(default=None, ge=1, le=20)
    reranker_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    crag_confident_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    offtopic_threshold: float | None = Field(default=None, ge=-1.0, le=1.0)
    llm: LlmOverrides | None = None


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    language: str | None = None
    strategy: str | None = None
    document_id: str | None = None
    document_ids: list[str] | None = None
    overrides: QueryOverrides | None = None


class Citation(BaseModel):
    number: int
    document_id: str
    chunk_id: str
    title: str
    source_uri: str
    page: int | None = None
    excerpt: str


class QueryTimings(BaseModel):
    total_ms: float
    stt_ms: float = 0
    guardrail_ms: float = 0
    embedding_ms: float = 0
    cache_ms: float = 0
    retrieval_ms: float = 0
    rerank_ms: float = 0
    crag_ms: float = 0
    generation_ms: float = 0

    @property
    def retrieval_pipeline_ms(self) -> float:
        """Everything except speech-to-text and token generation.

        This is the segment the sub-200ms latency target is measured against;
        generation time is reported separately because it is provider-bound.
        """
        return (
            self.guardrail_ms
            + self.embedding_ms
            + self.cache_ms
            + self.retrieval_ms
            + self.rerank_ms
            + self.crag_ms
        )


class GuardrailDecision(BaseModel):
    allowed: bool
    rule: GuardrailRule | None = None
    detail: str | None = None
    score: float | None = None


class CragTrace(BaseModel):
    action: CragAction
    top_score: float | None = None
    rewrites: int = 0
    rewritten_query: str | None = None
    kept_strips: int | None = None


class Transcript(BaseModel):
    text: str
    language_code: str | None = None
    provider: str
    model: str
    duration_ms: float = 0


class StageStatus(StrEnum):
    OK = "ok"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class PipelineStageTrace(BaseModel):
    id: str
    label: str
    status: StageStatus
    duration_ms: float = 0
    detail: str | None = None


class ChunkTrace(BaseModel):
    rank: int
    chunk_id: str
    document_id: str
    title: str
    score: float
    excerpt: str
    refined: bool = False


class GenerationTrace(BaseModel):
    provider: str | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class QueryTrace(BaseModel):
    query: str
    strategy: str
    language: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    profile: str = "local"
    collection_name: str | None = None
    content_version: str | None = None
    cache_namespace: str | None = None
    cache_status: CacheStatus = CacheStatus.MISS
    embedding_fingerprint: str | None = None
    reranker_fingerprint: str | None = None
    generator_model: str | None = None
    generator_provider: str | None = None
    stt_provider: str | None = None
    stt_model: str | None = None
    reranker_threshold: float | None = None
    crag_confident_threshold: float | None = None
    offtopic_threshold: float | None = None
    stages: list[PipelineStageTrace] = Field(default_factory=list)
    retrieved: list[ChunkTrace] = Field(default_factory=list)
    reranked: list[ChunkTrace] = Field(default_factory=list)
    contexts: list[ChunkTrace] = Field(default_factory=list)
    cited_chunk_ids: list[str] = Field(default_factory=list)
    candidate_k: int = 0
    context_top_k: int = 0
    abstention_reason: str | None = None
    generation: GenerationTrace | None = None
    overrides_applied: dict[str, Any] | None = None


class QueryResponse(BaseModel):
    query_id: str
    trace_id: str
    outcome: Outcome
    answer: str
    citations: list[Citation]
    cache_status: CacheStatus
    index_version: str
    timings: QueryTimings
    guardrail: GuardrailDecision | None = None
    crag: CragTrace | None = None
    transcript: Transcript | None = None
    generator_provider: str | None = None
    trace: QueryTrace | None = None


@dataclass(slots=True, frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    text: str
    title: str
    source_uri: str
    page: int | None = None
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RankedChunk:
    chunk: Chunk
    score: float


@dataclass(slots=True, frozen=True)
class ActiveIndex:
    content_version: str
    collection_name: str


@dataclass(slots=True, frozen=True)
class CachedAnswer:
    answer: str
    citations: tuple[Citation, ...]
    outcome: Outcome
    cache_status: CacheStatus
