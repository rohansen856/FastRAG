from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal, cast

from langfuse.types import TraceContext

ObservationType = Literal[
    "span",
    "generation",
    "agent",
    "tool",
    "chain",
    "retriever",
    "evaluator",
    "embedding",
    "guardrail",
]


class NullObservation:
    def update(self, **kwargs: Any) -> None:
        return None


def configure(settings: Any) -> None:
    """Publish FASTRAG_LANGFUSE_* settings under the names the SDK reads.

    The Langfuse client only looks at bare LANGFUSE_* variables, so the prefixed
    settings were previously parsed and then ignored. Copying them here means one
    documented variable name works for both.
    """
    if settings.langfuse_public_key:
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
    if settings.langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key.get_secret_value()
    if settings.langfuse_base_url:
        os.environ["LANGFUSE_HOST"] = settings.langfuse_base_url
    os.environ["LANGFUSE_TRACING_ENVIRONMENT"] = settings.environment
    os.environ["LANGFUSE_TRACING_ENABLED"] = "true" if settings.langfuse_enabled else "false"
    os.environ["FASTRAG_TRACE_RAW_CONTENT"] = "true" if settings.trace_raw_content else "false"


def trace_raw_content() -> bool:
    """Whether traces may carry document and answer text rather than hashes."""
    return os.getenv("FASTRAG_TRACE_RAW_CONTENT", "false").casefold() == "true"


@contextmanager
def observation(
    name: str,
    *,
    as_type: ObservationType = "span",
    trace_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Create a Langfuse observation without allowing telemetry failures to affect queries."""
    if (
        os.getenv("LANGFUSE_TRACING_ENABLED", "true").casefold() == "false"
        or not os.getenv("LANGFUSE_PUBLIC_KEY")
        or not os.getenv("LANGFUSE_SECRET_KEY")
    ):
        yield NullObservation()
        return
    try:
        from langfuse import get_client

        client = get_client()
    except Exception:
        yield NullObservation()
        return
    trace_context = cast(TraceContext, {"trace_id": trace_id}) if trace_id else None
    with client.start_as_current_observation(
        name=name,
        as_type=as_type,
        trace_context=trace_context,
        metadata=metadata,
    ) as current:
        yield current
