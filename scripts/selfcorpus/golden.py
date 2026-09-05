"""Derive the golden, calibration and cache-pair sets from the built corpus.

The model writes the *questions*; it never assigns the labels. `relevant_chunk_ids`
come from the chunker's own output for the section the question was written from,
so a label cannot drift from what was actually indexed. That is the same
discipline as MS MARCO's `is_selected`: real labels, mechanically applied.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

QA_SYSTEM = (
    "You write evaluation questions for a retrieval system indexing the FastRAG "
    "repository. Given one section of a file, write a specific question that this "
    "section alone answers, and a short factual answer drawn only from it. The "
    "question must name what it asks about; never write 'this function' or 'the "
    "above'. Return JSON matching the schema."
)

QA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "question": {"type": "string"},
        "answer": {"type": "string"},
    },
    "required": ["question", "answer"],
    "additionalProperties": False,
}

UNANSWERABLE_SYSTEM = (
    "You write questions that a documentation search system should refuse to "
    "answer. Given a topic that is NOT documented in the FastRAG repository, "
    "write a question that sounds like a plausible FastRAG question but whose "
    "answer is genuinely absent. Do not write nonsense or off-topic trivia: the "
    "question must be in-domain and specific. Return JSON matching the schema."
)

QUESTION_BATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"questions": {"type": "array", "items": {"type": "string"}}},
    "required": ["questions"],
    "additionalProperties": False,
}

UNANSWERABLE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"question": {"type": "string"}},
    "required": ["question"],
    "additionalProperties": False,
}

TRANSLATE_QUESTION_SYSTEM = (
    "Translate each numbered question into {language}. Return a JSON array with "
    "exactly one translation per question, in the same order. Keep identifiers, "
    "file paths, environment variables and code spans exactly as written."
)

# Absent capabilities, used to seed in-domain-but-unanswerable questions. These
# are near-misses on purpose: an obviously off-topic question is stopped by the
# text guardrail and never reaches the reranker, so it would calibrate nothing.
ABSENT_TOPICS: tuple[str, ...] = (
    "GraphQL subscription support",
    "a Kubernetes operator or Helm chart",
    "multi-tenant workspace isolation",
    "a built-in web crawler for ingesting sites",
    "fine-tuning the embedding model in-process",
    "an SMS or WhatsApp delivery channel",
    "automatic schema migration for user-defined payload fields",
    "a GUI for editing the system prompt",
    "role-based access control with per-user permissions",
    "streaming audio output / text-to-speech responses",
    "a Kafka or RabbitMQ event bus integration",
    "on-device inference for mobile clients",
)


@dataclass(slots=True)
class GoldenCandidate:
    id: str
    query: str
    reference_answer: str | None
    answerable: bool
    relevant_chunk_ids: list[str]
    category: str
    language: str
    document_key: str

    def as_record(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "reference_answer": self.reference_answer,
            "answerable": self.answerable,
            "relevant_chunk_ids": self.relevant_chunk_ids,
            "reference_contexts": [],
            "category": self.category,
            "language": self.language,
        }


def item_id(language: str, question: str) -> str:
    """Deterministic, so a re-run does not churn ids and collisions are impossible.

    `load_golden` rejects duplicate ids outright, and ids invented by a model
    collide constantly.
    """
    return f"self-{language}-{hashlib.sha1(question.encode()).hexdigest()[:10]}"


def chunk_ids_by_document(
    chunks: list[dict[str, Any]],
    strategy: str,
    key_by_id: dict[str, str],
    *,
    language: str | None = None,
) -> dict[str, list[str]]:
    """Map document key -> chunk ids, for the one strategy the golden set scores against.

    `evaluation.collect_records` and `calibrate.run` both retrieve with
    `chunk_strategy_list[0]`, so labels pointing at any other strategy's chunks
    score zero against every metric.

    Keyed on the language-independent document key rather than `document_id`, so
    the same lookup serves a question in any language once `language` selects
    which translation's chunks to return.
    """
    index: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        if chunk.get("strategy") != strategy:
            continue
        if language is not None and chunk.get("language") != language:
            continue
        key = key_by_id.get(str(chunk["document_id"]))
        if key is not None:
            index[key].append(str(chunk["chunk_id"]))
    return dict(index)


async def generate_answerable(
    generator: Any,
    documents: list[Any],
    chunk_index: dict[str, list[str]],
    *,
    concurrency: int = 1,
    min_words: int = 25,
    limit: int | None = None,
    priority_keys: set[str] | None = None,
    on_error: Any = None,
) -> list[GoldenCandidate]:
    """One question per section that actually produced chunks."""
    eligible = [
        document
        for document in documents
        if chunk_index.get(str(document.metadata["document_key"]))
        and len(document.text.split()) >= min_words
    ]
    if limit is not None and len(eligible) > limit:
        # Sections that were translated always get a question: they are the only
        # documents that can carry an answerable item in another language, and a
        # blind sample would usually miss them entirely.
        keys = priority_keys or set()
        required = [
            document
            for document in eligible
            if str(document.metadata["document_key"]) in keys
        ]
        rest = [document for document in eligible if document not in required]
        # Strided, not sliced: documents arrive grouped by file, so the first N
        # would cover a handful of modules and leave the rest of the corpus with
        # no questions at all.
        budget = max(0, limit - len(required))
        stride = max(1, len(rest) // budget) if budget else 1
        eligible = required + (rest[::stride][:budget] if budget else [])

    semaphore = asyncio.Semaphore(concurrency)
    results: list[GoldenCandidate] = []

    async def one(document: Any) -> None:
        chunk_ids = chunk_index.get(str(document.metadata["document_key"]))
        # A section that produced no chunks under the golden strategy cannot be
        # labelled; normalisation drops empty text, so this is not hypothetical.
        if not chunk_ids or len(document.text.split()) < min_words:
            return
        async with semaphore:
            try:
                result = await generator.complete_json(
                    system=QA_SYSTEM,
                    # A section's opening is enough to write a question about
                    # it, and the prompt is charged against a per-minute token
                    # quota on every one of a few hundred calls.
                    user=f"File: {document.title}\n\n{document.text[:2500]}",
                    schema=QA_SCHEMA,
                    schema_name="qa",
                    max_tokens=400,
                )
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                if on_error is not None:
                    on_error(document.title, exc)
                return
        question = str(result.get("question") or "").strip()
        answer = str(result.get("answer") or "").strip()
        if not question or not answer:
            return
        results.append(
            GoldenCandidate(
                id=item_id("en", question),
                query=question,
                reference_answer=answer,
                answerable=True,
                relevant_chunk_ids=chunk_ids,
                category=str(document.metadata.get("category", "documentation")),
                language="en",
                document_key=str(document.metadata["document_key"]),
            )
        )

    await asyncio.gather(*(one(document) for document in eligible))
    return results


async def generate_unanswerable(
    generator: Any, *, per_topic: int = 5, concurrency: int = 1, on_error: Any = None
) -> list[GoldenCandidate]:
    semaphore = asyncio.Semaphore(concurrency)
    results: list[GoldenCandidate] = []

    async def one(topic: str, variant: int) -> None:
        async with semaphore:
            try:
                result = await generator.complete_json(
                    system=UNANSWERABLE_SYSTEM,
                    user=f"Absent topic: {topic}\nVariant {variant}: ask about a different aspect.",
                    schema=UNANSWERABLE_SCHEMA,
                    schema_name="unanswerable",
                    max_tokens=200,
                )
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                if on_error is not None:
                    on_error(topic, exc)
                return
        question = str(result.get("question") or "").strip()
        if not question:
            return
        results.append(
            GoldenCandidate(
                id=item_id("en", question),
                query=question,
                reference_answer=None,
                answerable=False,
                relevant_chunk_ids=[],
                category="no-answer",
                language="en",
                document_key=f"absent:{topic}",
            )
        )

    await asyncio.gather(
        *(one(topic, variant) for topic in ABSENT_TOPICS for variant in range(per_topic))
    )
    return results


async def translate_questions(
    generator: Any,
    candidates: list[GoldenCandidate],
    translated_chunk_index: dict[str, dict[str, list[str]]],
    *,
    languages: list[str],
    concurrency: int = 1,
    batch_size: int = 8,
    on_error: Any = None,
) -> list[GoldenCandidate]:
    """Re-express questions in each Indic language against that language's chunks.

    An Indic item must point at translated-prose chunks. Code chunks are tagged
    `language=en`, so a Bengali question labelled with a code chunk becomes
    unretrievable the moment a language filter is applied.

    Questions are translated in batches: one call per question per language would
    be well over a thousand requests, which no free tier will serve in a day.
    """
    from .translate import LANGUAGE_NAMES

    semaphore = asyncio.Semaphore(concurrency)
    results: list[GoldenCandidate] = []

    async def run_batch(batch: list[GoldenCandidate], language: str) -> None:
        numbered = "\n".join(
            f"{index}. {candidate.query}" for index, candidate in enumerate(batch)
        )
        async with semaphore:
            try:
                result = await generator.complete_json(
                    system=TRANSLATE_QUESTION_SYSTEM.format(
                        language=LANGUAGE_NAMES[language]
                    ),
                    user=numbered,
                    schema=QUESTION_BATCH_SCHEMA,
                    schema_name="questions",
                    # Sized to the batch: a fixed reservation is charged against
                    # the per-minute token quota whether or not it is used.
                    max_tokens=len(numbered) // 2 + 256,
                )
            except Exception as exc:  # noqa: BLE001 - reported, not swallowed
                if on_error is not None:
                    on_error(language, exc)
                return
        questions = result.get("questions")
        # A dropped or merged entry would shift every question onto the wrong
        # chunks, so a shape mismatch discards the batch rather than guessing.
        if not isinstance(questions, list) or len(questions) != len(batch):
            if on_error is not None:
                on_error(language, RuntimeError("translated question count mismatch"))
            return
        for candidate, translated in zip(batch, questions, strict=True):
            question = str(translated).strip()
            if not question:
                continue
            results.append(
                GoldenCandidate(
                    id=item_id(language, question),
                    query=question,
                    reference_answer=candidate.reference_answer,
                    answerable=candidate.answerable,
                    relevant_chunk_ids=(
                        translated_chunk_index.get(language, {}).get(
                            candidate.document_key, []
                        )
                        if candidate.answerable
                        else []
                    ),
                    category=candidate.category,
                    language=language,
                    document_key=candidate.document_key,
                )
            )

    tasks = []
    for language in languages:
        eligible = [
            candidate
            for candidate in candidates
            # An answerable question with no chunks in this language cannot be
            # labelled, so it is not asked in that language at all.
            if not candidate.answerable
            or translated_chunk_index.get(language, {}).get(candidate.document_key)
        ]
        for start in range(0, len(eligible), batch_size):
            tasks.append(run_batch(eligible[start : start + batch_size], language))
    await asyncio.gather(*tasks)
    return [item for item in results if item.answerable is False or item.relevant_chunk_ids]


async def drop_leaking_unanswerables(
    candidates: list[GoldenCandidate],
    *,
    embedder: Any,
    retrieve: Any,
    reranker: Any,
    candidate_k: int,
    answerable_floor: float,
) -> tuple[list[GoldenCandidate], list[tuple[str, float]]]:
    """Verify each unanswerable against the built index rather than trusting the model.

    A file exclusion is not a semantic exclusion: this repository documents
    itself twice, so a question written from a held-out topic is often answered
    by a module docstring anyway. Each candidate is scored by the real retriever
    and reranker, and anything scoring like an answerable item is dropped as a
    leak. Answerable items are never filtered this way - pruning those would be
    tuning the golden set to pass its own gate.
    """
    kept: list[GoldenCandidate] = []
    leaks: list[tuple[str, float]] = []
    for candidate in candidates:
        vector = await embedder.embed_query(candidate.query)
        chunks = await retrieve(candidate.query, vector, candidate_k)
        ranked = await reranker.rerank(candidate.query, chunks, candidate_k)
        top = ranked[0].score if ranked else float("-inf")
        if top >= answerable_floor:
            leaks.append((candidate.query, top))
            continue
        kept.append(candidate)
    return kept, leaks


def split_pool(
    candidates: list[GoldenCandidate], *, calibration_fraction: float = 0.27
) -> tuple[list[GoldenCandidate], list[GoldenCandidate]]:
    """Split disjointly by source document, proportionally within each label class.

    Splitting by document rather than by row is what makes the calibration set
    genuinely held out: two questions written from the same section are near
    duplicates, and a section's translations restate it in five more languages,
    so letting any of them straddle the split leaks the regression set into the
    thresholds fitted against it. The shipped split had the stronger version of
    this bug - it was the first 40 rows of golden.jsonl, all Bengali.

    Answerable and unanswerable items are split separately and proportionally
    rather than by a shared hash bucket. There are only a dozen unanswerable
    topics, so hash bucketing them leaves the negative count to chance, and
    `choose_gate` needs roughly forty negatives before its 0.05 false-answer
    budget can tolerate even one false positive.
    """
    by_key: dict[str, list[GoldenCandidate]] = defaultdict(list)
    for candidate in candidates:
        by_key[candidate.document_key].append(candidate)

    def held_out(keys: list[str]) -> set[str]:
        # Ordered by hash so the choice is stable and unrelated to file order,
        # then taken by count so the proportion is exact rather than binomial.
        ordered = sorted(keys, key=lambda key: hashlib.sha1(key.encode()).hexdigest())
        return set(ordered[: round(calibration_fraction * len(ordered))])

    answerable_keys = [
        key for key, items in by_key.items() if any(item.answerable for item in items)
    ]
    unanswerable_keys = [key for key in by_key if key not in set(answerable_keys)]
    calibration_keys = held_out(answerable_keys) | held_out(unanswerable_keys)

    golden: list[GoldenCandidate] = []
    calibration: list[GoldenCandidate] = []
    for key, items in by_key.items():
        (calibration if key in calibration_keys else golden).extend(items)
    golden.sort(key=lambda item: item.id)
    calibration.sort(key=lambda item: item.id)
    return golden, calibration


def cache_pairs(
    candidates: list[GoldenCandidate],
    paraphrases: dict[str, str],
    *,
    max_negatives: int | None = None,
) -> list[dict[str, Any]]:
    """Paraphrase positives plus in-domain near-miss negatives.

    Random unrelated negatives are trivially separable and let
    `choose_cache_distance` settle on a uselessly permissive threshold. The pairs
    that actually pin the gate are two questions about *different* parts of the
    same file - close enough to be confusable, different enough that serving one
    answer for the other would be wrong.
    """
    positives = [
        {"left": candidate.query, "right": paraphrases[candidate.id], "equivalent": True}
        for candidate in candidates
        if paraphrases.get(candidate.id)
    ]

    answerable = [item for item in candidates if item.answerable]
    by_file: dict[str, list[GoldenCandidate]] = defaultdict(list)
    for candidate in answerable:
        by_file[f"{candidate.language}:{candidate.category}"].append(candidate)

    budget = max_negatives if max_negatives is not None else len(positives)
    negatives: list[dict[str, Any]] = []
    for group in by_file.values():
        for left, right in zip(group, group[1:], strict=False):
            if len(negatives) >= budget:
                break
            if left.document_key == right.document_key:
                continue
            negatives.append(
                {"left": left.query, "right": right.query, "equivalent": False}
            )
        if len(negatives) >= budget:
            break
    return positives + negatives


async def generate_paraphrases(
    generator: Any, candidates: list[GoldenCandidate], *, concurrency: int = 1
) -> dict[str, str]:
    """A genuine restatement of each question, for the semantic-cache positives.

    The shipped pairs used `"Please answer: " + query`, which shares almost every
    token and teaches the threshold nothing about real paraphrase distance.
    """
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, str] = {}

    async def one(candidate: GoldenCandidate) -> None:
        async with semaphore:
            try:
                result = await generator.complete_json(
                    system=(
                        "Restate this question so it means exactly the same thing but "
                        "shares as few words as possible with the original. Keep "
                        "identifiers and file paths. Return JSON."
                    ),
                    user=candidate.query,
                    schema=UNANSWERABLE_SCHEMA,
                    schema_name="question",
                    max_tokens=200,
                )
            except Exception:
                return
        question = str(result.get("question") or "").strip()
        if question and question != candidate.query:
            results[candidate.id] = question

    await asyncio.gather(*(one(candidate) for candidate in candidates))
    return results
