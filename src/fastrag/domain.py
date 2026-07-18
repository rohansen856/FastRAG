from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Outcome(StrEnum):
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"


class CacheStatus(StrEnum):
    MISS = "miss"
    EXACT = "exact"
    SEMANTIC = "semantic"


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)


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
    embedding_ms: float = 0
    cache_ms: float = 0
    retrieval_ms: float = 0
    rerank_ms: float = 0
    generation_ms: float = 0


class QueryResponse(BaseModel):
    query_id: str
    trace_id: str
    outcome: Outcome
    answer: str
    citations: list[Citation]
    cache_status: CacheStatus
    index_version: str
    timings: QueryTimings


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
