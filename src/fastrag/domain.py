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


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    language: str | None = None
    strategy: str | None = None


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
