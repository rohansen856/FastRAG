from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .calibration import Calibration
from .domain import QueryOverrides


@dataclass(frozen=True, slots=True)
class EffectiveQueryConfig:
    skip_cache: bool
    crag_enabled: bool
    candidate_k: int
    context_top_k: int
    calibration: Calibration
    generator_model: str
    max_answer_tokens: int
    llm_base_url: str
    llm_api_key: str
    llm_override_active: bool
    overrides_applied: dict[str, Any] | None


def resolve_effective_config(
    *,
    calibration: Calibration,
    crag_available: bool,
    candidate_k: int,
    context_top_k: int,
    generator_model: str,
    max_answer_tokens: int,
    llm_base_url: str,
    llm_api_key: str,
    overrides: QueryOverrides | None,
) -> EffectiveQueryConfig:
    skip_cache = bool(overrides and overrides.skip_cache)
    crag_enabled = (
        crag_available
        if overrides is None or overrides.crag_enabled is None
        else overrides.crag_enabled
    )
    resolved_candidate_k = (
        overrides.candidate_k if overrides and overrides.candidate_k is not None else candidate_k
    )
    resolved_context_top_k = (
        overrides.context_top_k
        if overrides and overrides.context_top_k is not None
        else context_top_k
    )
    if resolved_candidate_k < resolved_context_top_k:
        resolved_candidate_k = resolved_context_top_k

    effective_calibration = calibration
    if overrides:
        fields: dict[str, float] = {}
        if overrides.reranker_threshold is not None:
            fields["reranker_threshold"] = overrides.reranker_threshold
        if overrides.crag_confident_threshold is not None:
            fields["crag_confident_threshold"] = overrides.crag_confident_threshold
        if overrides.offtopic_threshold is not None:
            fields["offtopic_threshold"] = overrides.offtopic_threshold
        if fields:
            effective_calibration = replace(calibration, **fields)

    llm = overrides.llm if overrides else None
    resolved_model = llm.model if llm and llm.model else generator_model
    resolved_max_tokens = (
        llm.max_tokens if llm and llm.max_tokens is not None else max_answer_tokens
    )
    resolved_base_url = llm.base_url if llm and llm.base_url else llm_base_url
    resolved_api_key = llm.api_key if llm and llm.api_key else llm_api_key
    llm_override_active = bool(
        llm
        and llm_base_url
        and any(
            value is not None
            for value in (llm.base_url, llm.api_key, llm.model, llm.max_tokens)
        )
    )

    return EffectiveQueryConfig(
        skip_cache=skip_cache,
        crag_enabled=crag_enabled,
        candidate_k=resolved_candidate_k,
        context_top_k=resolved_context_top_k,
        calibration=effective_calibration,
        generator_model=resolved_model,
        max_answer_tokens=resolved_max_tokens,
        llm_base_url=resolved_base_url,
        llm_api_key=resolved_api_key,
        llm_override_active=llm_override_active,
        overrides_applied=redact_overrides_for_trace(overrides),
    )


def redact_overrides_for_trace(overrides: QueryOverrides | None) -> dict[str, Any] | None:
    if overrides is None:
        return None
    payload = overrides.model_dump(exclude_none=True, exclude_defaults=True)
    if not payload:
        return None
    llm = payload.get("llm")
    if isinstance(llm, dict) and llm.get("api_key"):
        llm = dict(llm)
        llm["api_key"] = "***"
        payload["llm"] = llm
    return payload


def has_overrides(overrides: QueryOverrides | None) -> bool:
    if overrides is None:
        return False
    return bool(overrides.model_dump(exclude_none=True))
