"""Corrective RAG.

Standard RAG generates from whatever retrieval returned. CRAG first grades that
context and takes a corrective action when it is weak, which is what stops a
confidently-worded answer being built on the wrong passage.

The grader here is the reranker score, not a second LLM call. That is deliberate:
an LLM grader would add hundreds of milliseconds to every query and this pipeline
has a 200ms retrieval budget. The reranker has already scored every candidate, so
grading is free; the two decision bands come from the calibration artifact.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .calibration import Calibration
from .domain import Chunk, CragAction, CragTrace, RankedChunk
from .harness import Deadline
from .metrics import CRAG_ACTIONS
from .text import split_sentences

REWRITE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "rewritten_query": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["rewritten_query", "reason"],
    "additionalProperties": False,
}

REWRITE_SYSTEM = (
    "You rewrite search queries for a multilingual retrieval system. "
    "Rewrite the user's question so it retrieves better: expand abbreviations, "
    "add the obvious entity names, and keep the original language of the question. "
    "Never answer the question. Return only the rewritten query."
)


@dataclass(frozen=True, slots=True)
class CragOutcome:
    action: CragAction
    ranked: list[RankedChunk]
    trace: CragTrace
    should_abstain: bool


class CorrectiveRetrieval:
    def __init__(
        self,
        *,
        calibration: Calibration,
        reranker: Any,
        retriever: Any,
        embedder: Any,
        generator: Any = None,
        enabled: bool = True,
        max_rewrites: int = 1,
        strip_min_tokens: int = 24,
        candidate_k: int = 20,
    ) -> None:
        self._calibration = calibration
        self._reranker = reranker
        self._retriever = retriever
        self._embedder = embedder
        self._generator = generator
        self._enabled = enabled
        self._max_rewrites = max_rewrites
        self._strip_min_tokens = strip_min_tokens
        self._candidate_k = candidate_k

    def grade(self, ranked: Sequence[RankedChunk]) -> CragAction:
        if not ranked:
            return CragAction.INCORRECT
        top = ranked[0].score
        if top >= self._calibration.crag_upper:
            return CragAction.CORRECT
        if top >= self._calibration.reranker_threshold:
            return CragAction.AMBIGUOUS
        return CragAction.INCORRECT

    async def run(
        self,
        query: str,
        ranked: list[RankedChunk],
        *,
        collection: str | None = None,
        strategy: str | None = None,
        language: str | None = None,
        deadline: Deadline | None = None,
        timings: dict[str, float] | None = None,
    ) -> CragOutcome:
        if not self._enabled:
            below = not ranked or ranked[0].score < self._calibration.reranker_threshold
            return CragOutcome(
                action=CragAction.DISABLED,
                ranked=ranked,
                trace=CragTrace(
                    action=CragAction.DISABLED,
                    top_score=ranked[0].score if ranked else None,
                ),
                should_abstain=below,
            )

        started = time.perf_counter()
        action = self.grade(ranked)
        CRAG_ACTIONS.labels(action=action.value).inc()

        if action is CragAction.CORRECT:
            outcome = CragOutcome(
                action=action,
                ranked=ranked,
                trace=CragTrace(action=action, top_score=ranked[0].score),
                should_abstain=False,
            )
        elif action is CragAction.AMBIGUOUS:
            outcome = await self._refine(query, ranked, deadline=deadline)
        else:
            outcome = await self._rewrite_and_retry(
                query,
                ranked,
                collection=collection,
                strategy=strategy,
                language=language,
                deadline=deadline,
            )

        if timings is not None:
            timings["crag"] = time.perf_counter() - started
        return outcome

    async def _refine(
        self, query: str, ranked: list[RankedChunk], *, deadline: Deadline | None
    ) -> CragOutcome:
        """Knowledge refinement: keep only the strips that actually carry signal.

        A passage can rank mid-band because one relevant sentence is buried in
        noise. Re-scoring sentence strips keeps that sentence and discards the
        rest, which measurably lifts faithfulness without another retrieval.
        """
        strips: list[tuple[int, str]] = []
        for index, item in enumerate(ranked[: self._candidate_k]):
            for sentence in split_sentences(item.chunk.text):
                if len(sentence.split()) >= 4:
                    strips.append((index, sentence))
        if not strips or not hasattr(self._reranker, "score"):
            return CragOutcome(
                action=CragAction.AMBIGUOUS,
                ranked=ranked,
                trace=CragTrace(action=CragAction.AMBIGUOUS, top_score=ranked[0].score),
                should_abstain=False,
            )

        scores = await self._reranker.score(query, [text for _, text in strips])
        threshold = self._calibration.reranker_threshold
        kept: dict[int, list[str]] = {}
        for (chunk_index, sentence), score in zip(strips, scores, strict=True):
            if score >= threshold:
                kept.setdefault(chunk_index, []).append(sentence)

        if not kept:
            return CragOutcome(
                action=CragAction.AMBIGUOUS,
                ranked=ranked,
                trace=CragTrace(
                    action=CragAction.AMBIGUOUS, top_score=ranked[0].score, kept_strips=0
                ),
                should_abstain=False,
            )

        refined: list[RankedChunk] = []
        for chunk_index, sentences in sorted(kept.items()):
            original = ranked[chunk_index]
            text = " ".join(sentences)
            # Keep short strips whole rather than truncating the source below the
            # point where it can still support a citation.
            if len(text.split()) < self._strip_min_tokens:
                refined.append(original)
                continue
            refined.append(
                RankedChunk(
                    chunk=Chunk(
                        chunk_id=original.chunk.chunk_id,
                        document_id=original.chunk.document_id,
                        text=text,
                        title=original.chunk.title,
                        source_uri=original.chunk.source_uri,
                        page=original.chunk.page,
                        score=original.chunk.score,
                        metadata={**original.chunk.metadata, "refined": True},
                    ),
                    score=original.score,
                )
            )
        return CragOutcome(
            action=CragAction.AMBIGUOUS,
            ranked=refined,
            trace=CragTrace(
                action=CragAction.AMBIGUOUS,
                top_score=ranked[0].score,
                kept_strips=sum(len(values) for values in kept.values()),
            ),
            should_abstain=False,
        )

    async def _rewrite_and_retry(
        self,
        query: str,
        ranked: list[RankedChunk],
        *,
        collection: str | None,
        strategy: str | None,
        language: str | None,
        deadline: Deadline | None,
    ) -> CragOutcome:
        top_score = ranked[0].score if ranked else None
        if self._max_rewrites < 1 or self._generator is None:
            return CragOutcome(
                action=CragAction.INCORRECT,
                ranked=ranked,
                trace=CragTrace(action=CragAction.INCORRECT, top_score=top_score),
                should_abstain=True,
            )
        try:
            rewritten = await self._rewrite(query, deadline=deadline)
        except Exception:
            # A failed rewrite must not turn into a fabricated answer.
            return CragOutcome(
                action=CragAction.INCORRECT,
                ranked=ranked,
                trace=CragTrace(action=CragAction.INCORRECT, top_score=top_score),
                should_abstain=True,
            )
        if not rewritten or rewritten.strip().casefold() == query.strip().casefold():
            return CragOutcome(
                action=CragAction.INCORRECT,
                ranked=ranked,
                trace=CragTrace(action=CragAction.INCORRECT, top_score=top_score),
                should_abstain=True,
            )

        vector = await self._embedder.embed_query(rewritten, deadline=deadline)
        candidates = await self._retriever.retrieve(
            rewritten,
            vector,
            self._candidate_k,
            collection=collection,
            strategy=strategy,
            language=language,
            deadline=deadline,
        )
        retried = await self._reranker.rerank(
            rewritten, candidates, self._candidate_k, deadline=deadline
        )
        CRAG_ACTIONS.labels(action="rewrite").inc()
        passed = bool(retried) and retried[0].score >= self._calibration.reranker_threshold
        return CragOutcome(
            action=CragAction.INCORRECT,
            ranked=retried if passed else ranked,
            trace=CragTrace(
                action=CragAction.INCORRECT,
                top_score=retried[0].score if retried else top_score,
                rewrites=1,
                rewritten_query=rewritten,
            ),
            should_abstain=not passed,
        )

    async def _rewrite(self, query: str, *, deadline: Deadline | None) -> str:
        result = await self._generator.complete_json(
            system=REWRITE_SYSTEM,
            user=f"Question: {query}",
            schema=REWRITE_SCHEMA,
            schema_name="query_rewrite",
            max_tokens=200,
            deadline=deadline,
        )
        return str(result.get("rewritten_query", "")).strip()
