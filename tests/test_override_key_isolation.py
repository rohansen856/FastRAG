"""A caller-chosen LLM endpoint must never receive the server's own API key."""

from __future__ import annotations

from fastrag.calibration import Calibration
from fastrag.domain import LlmOverrides, QueryOverrides
from fastrag.query_overrides import resolve_effective_config

SERVER_URL = "https://api.groq.com/openai/v1"
SERVER_KEY = "gsk-server-secret"


def _resolve(llm: LlmOverrides):
    return resolve_effective_config(
        calibration=Calibration(
            reranker_threshold=0.5,
            reranker_fingerprint="r",
            embedding_fingerprint="e",
            false_answer_rate=0.0,
            sample_count=30,
        ),
        crag_available=True,
        candidate_k=20,
        context_top_k=5,
        generator_model="openai/gpt-oss-20b",
        max_answer_tokens=800,
        llm_base_url=SERVER_URL,
        llm_api_key=SERVER_KEY,
        overrides=QueryOverrides(llm=llm),
    )


def test_foreign_base_url_without_a_key_gets_no_key() -> None:
    """Otherwise `{"llm": {"base_url": "https://attacker"}}` exfiltrates the Groq key."""
    effective = _resolve(LlmOverrides(base_url="https://attacker.example/v1"))
    assert effective.llm_base_url == "https://attacker.example/v1"
    assert SERVER_KEY not in effective.llm_api_key


def test_foreign_base_url_uses_the_callers_own_key() -> None:
    effective = _resolve(LlmOverrides(base_url="https://other.example/v1", api_key="caller-key"))
    assert effective.llm_api_key == "caller-key"


def test_same_provider_model_override_keeps_the_server_key() -> None:
    """Switching model on the server's own endpoint is what the Experiment panel does."""
    effective = _resolve(LlmOverrides(model="openai/gpt-oss-120b"))
    assert effective.llm_base_url == SERVER_URL
    assert effective.llm_api_key == SERVER_KEY


def test_trailing_slash_is_still_the_server_endpoint() -> None:
    effective = _resolve(LlmOverrides(base_url=SERVER_URL + "/", model="m"))
    assert effective.llm_api_key == SERVER_KEY
