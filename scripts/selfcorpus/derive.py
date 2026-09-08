"""Derive an evaluation set from corpus structure alone, with no generator calls.

The generator-written questions in `golden.py` read better and probe harder, but
they cost a token quota that a free tier will not always have. This module builds
the same record shape out of what the repository already states about itself: a
Markdown heading names its section, a Python symbol names itself, and a docstring
summarises it.

The trade-off is explicit and matters when reading the numbers: a heading-derived
question shares vocabulary with the chunk it points at, so retrieval finds it more
easily than a real user's phrasing would. Thresholds fitted on this are optimistic.
Treat it as a bootstrap that lets a freshly indexed corpus be served at all, and
replace it with `golden.py` output when quota allows.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .golden import ABSENT_TOPICS, GoldenCandidate, item_id

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
_CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)


def _summary(text: str, *, sentences: int = 2, limit: int = 400) -> str:
    """The opening prose of a section, minus headings and code fences."""
    body = _CODE_FENCE.sub(" ", text)
    body = _HEADING.sub("", body)
    cleaned = " ".join(body.split())
    parts = [part for part in _SENTENCE_END.split(cleaned) if part.strip()]
    return " ".join(parts[:sentences])[:limit].strip()


def _question(document: Any) -> str | None:
    """Phrase a question from what the document already calls itself."""
    section = str(document.metadata.get("section") or "").strip()
    repo_path = str(document.metadata.get("repo_path") or "")
    name = Path(repo_path).name
    if not section or not name:
        return None
    if repo_path.endswith(".py"):
        if section == "module header":
            return f"What is the module {name} responsible for in FastRAG?"
        return f"What does {section} in {name} do?"
    if section == Path(name).stem:  # the file's preamble, not a real heading
        return f"What does the {name} documentation cover?"
    return f"In FastRAG's {name}, what does the section on {section} explain?"


def derive_answerable(
    documents: list[Any],
    chunk_index: dict[str, list[str]],
    *,
    limit: int | None = None,
    min_words: int = 40,
) -> list[GoldenCandidate]:
    candidates: list[GoldenCandidate] = []
    for document in documents:
        key = str(document.metadata["document_key"])
        chunk_ids = chunk_index.get(key)
        if not chunk_ids or len(document.text.split()) < min_words:
            continue
        query = _question(document)
        answer = _summary(document.text)
        # An answerable record needs both an answer and chunks, or GoldenItem
        # rejects it outright.
        if not query or len(answer.split()) < 8:
            continue
        candidates.append(
            GoldenCandidate(
                id=item_id("en", query),
                query=query,
                reference_answer=answer,
                answerable=True,
                relevant_chunk_ids=chunk_ids,
                category=str(document.metadata.get("category", "documentation")),
                language="en",
                document_key=key,
            )
        )
    if limit is not None and len(candidates) > limit:
        stride = max(1, len(candidates) // limit)
        candidates = candidates[::stride][:limit]
    return candidates


# Phrasings applied to each absent capability, so the negatives vary in shape
# rather than being one template repeated.
_ABSENT_FORMS = (
    "How does FastRAG handle {topic}?",
    "Which module in FastRAG implements {topic}?",
    "How do I configure {topic} in FastRAG?",
    "What are the defaults for {topic} in FastRAG?",
    "Where is {topic} documented for FastRAG?",
    "What does FastRAG's {topic} cost at scale?",
    "Which environment variable enables {topic} in FastRAG?",
    "How do I troubleshoot {topic} in FastRAG?",
)


def derive_unanswerable(*, per_topic: int = 5) -> list[GoldenCandidate]:
    """In-domain questions about capabilities the repository does not have.

    In-domain on purpose: an obviously off-topic question is stopped by the text
    guardrail and returns `refused` without ever reaching the reranker, so it
    would score as a correct abstention while calibrating nothing.
    """
    candidates: list[GoldenCandidate] = []
    for topic in ABSENT_TOPICS:
        for index in range(min(per_topic, len(_ABSENT_FORMS))):
            query = _ABSENT_FORMS[index].format(topic=topic)
            candidates.append(
                GoldenCandidate(
                    id=item_id("en", query),
                    query=query,
                    reference_answer=None,
                    answerable=False,
                    relevant_chunk_ids=[],
                    category="no-answer",
                    language="en",
                    document_key=f"absent:{topic}",
                )
            )
    return candidates
