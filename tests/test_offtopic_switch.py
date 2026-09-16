"""The centroid off-topic gate can be switched off without touching the other guardrails."""

from __future__ import annotations

from fastrag.bootstrap import offtopic_centroid
from fastrag.config import Settings
from fastrag.guardrails import Guardrails


def test_disabled_gate_drops_the_centroid_only() -> None:
    """E5 scores ~0.8 against the centroid for on- and off-topic text alike."""
    centroid = [1.0, 0.0]
    assert offtopic_centroid(Settings(guardrail_offtopic_enabled=True), centroid) == centroid
    assert offtopic_centroid(Settings(guardrail_offtopic_enabled=False), centroid) is None


def test_guardrails_without_a_centroid_allow_every_vector() -> None:
    guardrails = Guardrails(enabled=True, corpus_centroid=None, offtopic_threshold=0.99)
    assert guardrails.check_vector([0.0, 1.0], offtopic_threshold=0.99).allowed
