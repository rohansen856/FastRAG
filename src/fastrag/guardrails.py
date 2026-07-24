"""Input-side guardrails.

The pipeline already refuses to answer ungrounded questions on the way out, via
calibrated abstention and sentence-level citation validation. These rules run on
the way in, so obviously unanswerable or hostile input is rejected before it costs
an embedding call, a retrieval, and a generation.

Ordering is deliberate and cheapest-first: pure string checks, then a vector
comparison that reuses the embedding the pipeline already needed, and only then
(optionally) a model call.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from .domain import GuardrailDecision, GuardrailRule
from .harness import Deadline
from .metrics import GUARDRAIL_BLOCKS
from .text import detect_script_language

ALLOWED = GuardrailDecision(allowed=True)

INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bignore\s+(?:all\s+)?(?:the\s+)?previous\s+(?:instructions|prompts?|rules?)\b",
        r"\bdisregard\s+(?:all\s+)?(?:the\s+)?(?:above|previous|prior|system)\b",
        r"\byou\s+are\s+now\s+(?:a|an|in)\b.{0,40}\bmode\b",
        r"\b(?:reveal|print|show|repeat|output)\s+(?:me\s+)?(?:your\s+)?"
        r"(?:system\s+prompt|initial\s+instructions|hidden\s+rules)\b",
        r"\bdeveloper\s+mode\b",
        r"\bDAN\s+mode\b",
        r"<\s*/?\s*(?:system|assistant)\s*>",
        r"\[\s*(?:system|assistant)\s*\]",
    )
)

UNSAFE_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bhow\s+(?:do\s+i|to|can\s+i)\b.{0,60}\b(?:make|build|synthesi[sz]e|construct)\b"
        r".{0,40}\b(?:bomb|explosive|nerve\s+agent|bioweapon|meth(?:amphetamine)?)\b",
        r"\b(?:kill|murder|poison)\s+(?:my|a|an|someone|somebody|him|her|them)\b",
        r"\bchild\s+(?:porn|sexual\s+abuse)\b",
        r"\bhow\s+to\s+(?:hack|ddos|breach)\b.{0,40}\b(?:bank|hospital|government|grid)\b",
    )
)

SAFETY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "unsafe": {"type": "boolean"},
        "category": {"type": "string"},
    },
    "required": ["unsafe", "category"],
    "additionalProperties": False,
}

SAFETY_SYSTEM = (
    "You classify whether a user question requests content that is unsafe to answer: "
    "weapons of mass destruction, targeted violence, sexual content involving minors, "
    "or attacks on critical infrastructure. Ordinary questions, including sensitive or "
    "controversial factual ones, are safe. Respond with the JSON schema only."
)

REFUSALS: dict[GuardrailRule, str] = {
    GuardrailRule.OFF_TOPIC: (
        "That question is outside the knowledge base I have been given, so I can't answer it."
    ),
    GuardrailRule.UNSAFE: "I can't help with that request.",
    GuardrailRule.PROMPT_INJECTION: (
        "I can only answer questions about the indexed sources, so I can't follow that instruction."
    ),
    GuardrailRule.UNSUPPORTED_LANGUAGE: (
        "I can't answer in that language yet. Supported languages are English, Hindi, "
        "Bengali, Tamil, Telugu and Marathi."
    ),
    GuardrailRule.EMPTY: "I didn't catch a question there. Could you try again?",
}


def refusal_text(rule: GuardrailRule) -> str:
    return REFUSALS.get(rule, "I can't answer that.")


def _blocked(rule: GuardrailRule, detail: str, score: float | None = None) -> GuardrailDecision:
    GUARDRAIL_BLOCKS.labels(rule=rule.value).inc()
    return GuardrailDecision(allowed=False, rule=rule, detail=detail, score=score)


class Guardrails:
    def __init__(
        self,
        *,
        enabled: bool = True,
        languages: set[str] | None = None,
        corpus_centroid: Sequence[float] | None = None,
        offtopic_threshold: float | None = None,
        safety_generator: Any = None,
    ) -> None:
        self._enabled = enabled
        self._languages = languages or set()
        self._centroid = list(corpus_centroid) if corpus_centroid else None
        self._offtopic_threshold = offtopic_threshold
        self._safety_generator = safety_generator

    def check_text(self, query: str) -> GuardrailDecision:
        """String-only rules. No network, no model, runs in microseconds."""
        if not self._enabled:
            return ALLOWED
        stripped = query.strip()
        if not stripped:
            return _blocked(GuardrailRule.EMPTY, "empty query")
        for pattern in INJECTION_PATTERNS:
            if pattern.search(stripped):
                return _blocked(GuardrailRule.PROMPT_INJECTION, "instruction-override pattern")
        for pattern in UNSAFE_PATTERNS:
            if pattern.search(stripped):
                return _blocked(GuardrailRule.UNSAFE, "matched unsafe-content pattern")
        if self._languages:
            language = detect_script_language(stripped)
            if language != "unknown" and language not in self._languages:
                return _blocked(GuardrailRule.UNSUPPORTED_LANGUAGE, f"detected language {language}")
        return ALLOWED

    def check_vector(self, vector: Sequence[float]) -> GuardrailDecision:
        """Off-topic detection against the corpus centroid.

        This reuses the query embedding the pipeline computed anyway, so the
        added cost is a dot product rather than another provider round trip.
        """
        if not self._enabled or self._centroid is None or self._offtopic_threshold is None:
            return ALLOWED
        similarity = _cosine(vector, self._centroid)
        if similarity < self._offtopic_threshold:
            return _blocked(
                GuardrailRule.OFF_TOPIC,
                "query is far from the indexed corpus",
                score=similarity,
            )
        return ALLOWED

    async def check_safety_model(
        self, query: str, *, deadline: Deadline | None = None
    ) -> GuardrailDecision:
        """Optional model-backed safety pass for input the patterns did not settle."""
        if not self._enabled or self._safety_generator is None:
            return ALLOWED
        try:
            result = await self._safety_generator.complete_json(
                system=SAFETY_SYSTEM,
                user=f"Question: {query}",
                schema=SAFETY_SCHEMA,
                schema_name="safety",
                max_tokens=64,
                deadline=deadline,
            )
        except Exception:
            # Fail open: a classifier outage must not take the whole service down.
            # The output-side grounding guardrails still apply.
            return ALLOWED
        if bool(result.get("unsafe")):
            return _blocked(GuardrailRule.UNSAFE, str(result.get("category") or "model-flagged"))
        return ALLOWED


def corpus_centroid(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        return []
    dimension = len(vectors[0])
    totals = [0.0] * dimension
    for vector in vectors:
        for index, value in enumerate(vector):
            totals[index] += value
    centroid = [value / len(vectors) for value in totals]
    magnitude = sum(value * value for value in centroid) ** 0.5
    return centroid if magnitude == 0 else [value / magnitude for value in centroid]


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return float(dot / (left_norm * right_norm))
