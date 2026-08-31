from __future__ import annotations

import re
from collections.abc import Sequence

from .chunking import display_text_of
from .domain import Chunk, Citation
from .text import SENTENCE_TERMINATORS

MARKER_RE = re.compile(r"\[C:([A-Za-z0-9_.:-]+)\]")
MARKER_LOOSE_RE = re.compile(r"\[\s*C:([A-Za-z0-9_.:-]+)\s*\]")
NUMBERED_RE = re.compile(r"\[(\d+)\]")
# Split only when the next sentence has clearly started, so `fact. [C:id]`
# stays one unit. Look behind a terminator or a closing marker bracket.
_SENTENCE_SPLIT_RE = re.compile(
    rf"(?:(?<=[{re.escape(SENTENCE_TERMINATORS)}])|(?<=\]))\s+(?=[^\s\[])"
)


class CitationValidationError(ValueError):
    pass


class SentenceCitationBuffer:
    """Buffers model output until complete, source-validated sentences are available."""

    def __init__(self, contexts: Sequence[Chunk], *, auto_cite: bool = False) -> None:
        self._contexts = {chunk.chunk_id: chunk for chunk in contexts}
        self._context_order = [chunk.chunk_id for chunk in contexts]
        self._numbers: dict[str, int] = {}
        self._buffer = ""
        self._auto_cite = auto_cite
        self._default_chunk_id = self._pick_default_chunk_id()

    def _pick_default_chunk_id(self) -> str | None:
        if not self._context_order:
            return None
        if len(self._context_order) == 1 or self._auto_cite:
            return self._context_order[0]
        return None

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        if not MARKER_RE.search(self._normalize_text(self._buffer)):
            return []
        parts = _SENTENCE_SPLIT_RE.split(self._buffer)
        if len(parts) == 1:
            return []
        self._buffer = parts.pop()
        complete = [part for part in parts if part.strip()]
        if not complete:
            return []
        batch = list(complete)
        if self._buffer.strip() and MARKER_RE.search(self._normalize_text(self._buffer)):
            batch.append(self._buffer.strip())
            self._buffer = ""
        if not _trailing_markers([self._normalize_text(part) for part in batch]):
            if self._default_chunk_id is None:
                return []
        return self._validate_batch(batch)

    def finish(self) -> list[str]:
        leftover = self._buffer.strip()
        self._buffer = ""
        if not leftover:
            return []
        normalized = self._normalize_text(leftover)
        if not MARKER_RE.search(normalized) and self._default_chunk_id is not None:
            leftover = f"{leftover} [C:{self._default_chunk_id}]"
        parts = [part for part in _SENTENCE_SPLIT_RE.split(leftover) if part.strip()]
        if not parts:
            return []
        return self._validate_batch(parts)

    def salvage(self, raw_answer: str) -> list[str]:
        """Re-parse a complete model answer with auto-cite forced (attached docs)."""
        saved_auto = self._auto_cite
        saved_default = self._default_chunk_id
        self._auto_cite = True
        self._default_chunk_id = self._pick_default_chunk_id() or saved_default
        self._buffer = raw_answer.strip()
        try:
            rendered = self.finish()
        finally:
            self._auto_cite = saved_auto
            self._default_chunk_id = saved_default
            self._buffer = ""
        return rendered

    def citations(self) -> list[Citation]:
        ordered = sorted(self._numbers.items(), key=lambda item: item[1])
        return [self._citation(self._contexts[chunk_id], number) for chunk_id, number in ordered]

    def _map_numbered_citations(self, text: str) -> str:
        if not self._context_order:
            return text

        def repl(match: re.Match[str]) -> str:
            index = int(match.group(1))
            if 1 <= index <= len(self._context_order):
                return f"[C:{self._context_order[index - 1]}]"
            return match.group(0)

        return NUMBERED_RE.sub(repl, text)

    def _normalize_text(self, text: str) -> str:
        text = MARKER_LOOSE_RE.sub(lambda match: f"[C:{match.group(1)}]", text)
        text = self._map_numbered_citations(text)
        if len(self._context_order) == 1:
            chunk_id = self._context_order[0]
            text = MARKER_RE.sub(
                lambda match: match.group(0)
                if match.group(1) in self._contexts
                else f"[C:{chunk_id}]",
                text,
            )
        return text

    def _validate_batch(self, parts: Sequence[str]) -> list[str]:
        trailing = _trailing_markers([self._normalize_text(part) for part in parts])
        if not trailing and self._default_chunk_id is not None:
            trailing = [self._default_chunk_id]
        if not trailing:
            raise CitationValidationError("generated sentence has no citation marker")
        suffix = " " + " ".join(f"[C:{chunk_id}]" for chunk_id in trailing)
        rendered: list[str] = []
        for part in parts:
            sentence = self._normalize_text(part.strip())
            if not sentence:
                continue
            if not MARKER_RE.search(sentence):
                sentence = f"{sentence}{suffix}"
            rendered.append(self._validate_and_render(sentence))
        return rendered

    def _validate_and_render(self, sentence: str) -> str:
        sentence = self._normalize_text(sentence)
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
        # Verbatim where available, so a quoted code chunk keeps its line breaks
        # and indentation instead of arriving as one collapsed line.
        excerpt = display_text_of(chunk)[:320]
        return Citation(
            number=number,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            source_uri=chunk.source_uri,
            page=chunk.page,
            excerpt=excerpt,
        )


def _trailing_markers(parts: Sequence[str]) -> list[str]:
    for part in reversed(parts):
        markers = MARKER_RE.findall(part)
        if markers:
            return markers
    return []
