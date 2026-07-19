from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import Chunk, Citation

MARKER_RE = re.compile(r"\[C:([A-Za-z0-9_.:-]+)\]")
SENTENCE_END_RE = re.compile(r"(?<=[.!?])(?:\s+|$)|\n+")


class CitationValidationError(ValueError):
    pass


class SentenceCitationBuffer:
    """Buffers model output until complete, source-validated sentences are available."""

    def __init__(self, contexts: Sequence[Chunk]) -> None:
        self._contexts = {chunk.chunk_id: chunk for chunk in contexts}
        self._numbers: dict[str, int] = {}
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        parts = SENTENCE_END_RE.split(self._buffer)
        if len(parts) == 1:
            return []
        self._buffer = parts.pop()
        return [self._validate_and_render(part) for part in parts if part.strip()]

    def finish(self) -> list[str]:
        if not self._buffer.strip():
            return []
        rendered = self._validate_and_render(self._buffer)
        self._buffer = ""
        return [rendered]

    def citations(self) -> list[Citation]:
        ordered = sorted(self._numbers.items(), key=lambda item: item[1])
        return [self._citation(self._contexts[chunk_id], number) for chunk_id, number in ordered]

    def _validate_and_render(self, sentence: str) -> str:
        markers = MARKER_RE.findall(sentence)
        if not markers:
            raise CitationValidationError("generated sentence has no citation marker")
        for chunk_id in markers:
            if chunk_id not in self._contexts:
                raise CitationValidationError(f"unknown citation marker: {chunk_id}")
            self._numbers.setdefault(chunk_id, len(self._numbers) + 1)
        return MARKER_RE.sub(lambda match: f"[{self._numbers[match.group(1)]}]", sentence).strip()

    @staticmethod
    def _citation(chunk: Chunk, number: int) -> Citation:
        excerpt = " ".join(chunk.text.split())[:320]
        return Citation(
            number=number,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            source_uri=chunk.source_uri,
            page=chunk.page,
            excerpt=excerpt,
        )
