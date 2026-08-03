from __future__ import annotations

import re
from collections.abc import Sequence

from .domain import Chunk, Citation
from .text import SENTENCE_TERMINATORS

MARKER_RE = re.compile(r"\[C:([A-Za-z0-9_.:-]+)\]")
# Split only when the next sentence has clearly started, so `fact. [C:id]`
# stays one unit. Look behind a terminator or a closing marker bracket.
_SENTENCE_SPLIT_RE = re.compile(
    rf"(?:(?<=[{re.escape(SENTENCE_TERMINATORS)}])|(?<=\]))\s+(?=[^\s\[])"
)


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
        parts = _SENTENCE_SPLIT_RE.split(self._buffer)
        if len(parts) == 1:
            return []
        self._buffer = parts.pop()
        return [self._validate_and_render(part) for part in parts if part.strip()]

    def finish(self) -> list[str]:
        leftover = self._buffer.strip()
        self._buffer = ""
        if not leftover:
            return []
        return [self._validate_and_render(leftover)]

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
