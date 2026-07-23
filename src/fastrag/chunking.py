"""Chunking strategies.

Different corpora reward different splits, and MS MARCO passages are short and
self-contained while ingested PDFs are long and structured. Rather than pick one,
every strategy writes a `strategy` field into the Qdrant payload so several can
live in one collection and be compared at query time with a filter.

Two strategies separate what is *indexed* from what is *generated from*:
`sentence_window` indexes a narrow span for retrieval precision but returns the
surrounding window, and `hierarchical` retrieves child chunks but returns the
parent. Both express this through `context_text` in the chunk metadata.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from .domain import Chunk
from .text import detect_script_language, normalize_text, split_sentences

CONTEXT_TEXT_KEY = "context_text"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    document_id: str
    text: str
    title: str
    source_uri: str
    page: int | None = None
    language: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TextChunk:
    """A chunk before embedding.

    `text` is embedded and cited; `context_text` (when different) is what the
    generator actually reads.
    """

    text: str
    strategy: str
    context_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ChunkingStrategy(Protocol):
    name: str

    async def split(self, document: SourceDocument) -> list[TextChunk]: ...


def context_of(chunk: Chunk) -> str:
    """Text handed to the generator, which may be wider than the indexed span."""
    value = chunk.metadata.get(CONTEXT_TEXT_KEY)
    return str(value) if value else chunk.text


def _word_windows(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= size:
        return [" ".join(words)]
    step = max(1, size - overlap)
    windows = []
    for start in range(0, len(words), step):
        window = words[start : start + size]
        if not window:
            break
        windows.append(" ".join(window))
        if start + size >= len(words):
            break
    return windows


class FixedChunking:
    """Uniform word windows with overlap. The baseline everything else is measured against."""

    name = "fixed"

    def __init__(self, *, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        self._size = chunk_size
        self._overlap = chunk_overlap

    async def split(self, document: SourceDocument) -> list[TextChunk]:
        return [
            TextChunk(text=window, strategy=self.name)
            for window in _word_windows(document.text, self._size, self._overlap)
        ]


class SentenceChunking:
    """Packs whole sentences up to a budget, never splitting mid-sentence."""

    name = "sentence"

    def __init__(self, *, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        self._size = chunk_size
        self._overlap = chunk_overlap

    async def split(self, document: SourceDocument) -> list[TextChunk]:
        sentences = split_sentences(document.text)
        if not sentences:
            return []
        chunks: list[TextChunk] = []
        current: list[str] = []
        current_words = 0
        for sentence in sentences:
            words = len(sentence.split())
            if current and current_words + words > self._size:
                chunks.append(TextChunk(text=" ".join(current), strategy=self.name))
                # Carry trailing sentences forward so a fact spanning a boundary
                # still appears whole in at least one chunk.
                carry: list[str] = []
                carried = 0
                for previous in reversed(current):
                    previous_words = len(previous.split())
                    if carried + previous_words > self._overlap:
                        break
                    carry.insert(0, previous)
                    carried += previous_words
                current = carry
                current_words = carried
            current.append(sentence)
            current_words += words
        if current:
            chunks.append(TextChunk(text=" ".join(current), strategy=self.name))
        return chunks


class SentenceWindowChunking:
    """Indexes one sentence, generates from its neighbours.

    Embedding a single sentence keeps the vector tightly focused, which improves
    retrieval precision, while the returned window restores the context the
    sentence needs to actually be answerable.
    """

    name = "sentence_window"

    def __init__(self, *, window: int = 3) -> None:
        self._window = window

    async def split(self, document: SourceDocument) -> list[TextChunk]:
        sentences = split_sentences(document.text)
        chunks: list[TextChunk] = []
        for index, sentence in enumerate(sentences):
            start = max(0, index - self._window)
            end = min(len(sentences), index + self._window + 1)
            chunks.append(
                TextChunk(
                    text=sentence,
                    strategy=self.name,
                    context_text=" ".join(sentences[start:end]),
                    metadata={"window": self._window, "sentence_index": index},
                )
            )
        return chunks


class SemanticChunking:
    """Splits where meaning shifts rather than where a token budget runs out.

    Consecutive sentences are embedded and cut wherever similarity drops below a
    percentile of the observed distribution, so the threshold adapts per document
    instead of being a fixed constant that suits one corpus and not another.
    """

    name = "semantic"

    def __init__(
        self,
        embedder: Any,
        *,
        breakpoint_percentile: float = 0.25,
        max_words: int = 400,
        min_sentences: int = 2,
    ) -> None:
        self._embedder = embedder
        self._percentile = breakpoint_percentile
        self._max_words = max_words
        self._min_sentences = min_sentences

    async def split(self, document: SourceDocument) -> list[TextChunk]:
        sentences = split_sentences(document.text)
        if len(sentences) <= self._min_sentences:
            return [TextChunk(text=document.text.strip(), strategy=self.name)] if sentences else []
        vectors = await self._embedder.embed_documents(sentences)
        similarities = [
            _cosine(vectors[index], vectors[index + 1]) for index in range(len(vectors) - 1)
        ]
        cut = _percentile(similarities, self._percentile)
        chunks: list[TextChunk] = []
        current = [sentences[0]]
        for index, similarity in enumerate(similarities):
            words = sum(len(part.split()) for part in current)
            if similarity < cut or words >= self._max_words:
                chunks.append(TextChunk(text=" ".join(current), strategy=self.name))
                current = []
            current.append(sentences[index + 1])
        if current:
            chunks.append(TextChunk(text=" ".join(current), strategy=self.name))
        return chunks


class HierarchicalChunking:
    """Small children for retrieval, large parents for generation.

    Retrieval matches a precise child; the generator receives the parent so the
    answer is not starved of surrounding context.
    """

    name = "hierarchical"

    def __init__(self, *, parent_size: int = 900, child_size: int = 220, overlap: int = 40) -> None:
        self._parent_size = parent_size
        self._child_size = child_size
        self._overlap = overlap

    async def split(self, document: SourceDocument) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        for parent_index, parent in enumerate(_word_windows(document.text, self._parent_size, 0)):
            parent_id = hashlib.sha256(parent.encode()).hexdigest()[:16]
            for child in _word_windows(parent, self._child_size, self._overlap):
                chunks.append(
                    TextChunk(
                        text=child,
                        strategy=self.name,
                        context_text=parent,
                        metadata={"parent_id": parent_id, "parent_index": parent_index},
                    )
                )
        return chunks


class MetadataAwareChunking:
    """Prepends a provenance header to the embedded text.

    A bare MS MARCO passage often lacks the entity it is about. Embedding
    "title | language | source" alongside the passage restores that signal, while
    the citation excerpt still shows the untouched passage.
    """

    name = "metadata_aware"

    def __init__(self, *, chunk_size: int = 400, chunk_overlap: int = 50) -> None:
        self._inner = SentenceChunking(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    async def split(self, document: SourceDocument) -> list[TextChunk]:
        header_parts = [document.title]
        if document.language:
            header_parts.append(document.language)
        for key in ("section", "query", "category"):
            value = document.metadata.get(key)
            if value:
                header_parts.append(str(value))
        header = " | ".join(part for part in header_parts if part)
        chunks = await self._inner.split(document)
        return [
            TextChunk(
                text=f"{header}\n{chunk.text}" if header else chunk.text,
                strategy=self.name,
                context_text=chunk.text,
                metadata={"header": header},
            )
            for chunk in chunks
        ]


STRATEGY_NAMES = (
    FixedChunking.name,
    SentenceChunking.name,
    SentenceWindowChunking.name,
    SemanticChunking.name,
    HierarchicalChunking.name,
    MetadataAwareChunking.name,
)


def build_strategy(
    name: str,
    *,
    embedder: Any = None,
    chunk_size: int = 400,
    chunk_overlap: int = 50,
) -> ChunkingStrategy:
    if name == FixedChunking.name:
        return FixedChunking(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if name == SentenceChunking.name:
        return SentenceChunking(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if name == SentenceWindowChunking.name:
        return SentenceWindowChunking()
    if name == SemanticChunking.name:
        if embedder is None:
            raise ValueError("semantic chunking requires an embedder")
        return SemanticChunking(embedder, max_words=chunk_size)
    if name == HierarchicalChunking.name:
        return HierarchicalChunking()
    if name == MetadataAwareChunking.name:
        return MetadataAwareChunking(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    raise ValueError(f"unknown chunking strategy: {name}")


async def chunk_document(
    document: SourceDocument, strategies: Sequence[ChunkingStrategy]
) -> list[dict[str, Any]]:
    """Run every strategy over one document and emit Qdrant-ready payloads."""
    payloads: list[dict[str, Any]] = []
    language = document.language or detect_script_language(document.text)
    for strategy in strategies:
        for index, chunk in enumerate(await strategy.split(document)):
            text = normalize_text(chunk.text)
            if not text:
                continue
            chunk_id = str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"{document.document_id}:{strategy.name}:{text}")
            )
            payload: dict[str, Any] = {
                "chunk_id": chunk_id,
                "document_id": document.document_id,
                "text": text,
                "title": document.title,
                "source_uri": document.source_uri,
                "page": document.page,
                "strategy": strategy.name,
                "language": language,
                "position": index,
            }
            if chunk.context_text and chunk.context_text != chunk.text:
                payload[CONTEXT_TEXT_KEY] = normalize_text(chunk.context_text)
            payload.update(chunk.metadata)
            payloads.append(payload)
    return payloads


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(dot / (left_norm * right_norm))


def _percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * fraction)))
    return float(ordered[index])
