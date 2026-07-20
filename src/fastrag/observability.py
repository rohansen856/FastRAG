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
