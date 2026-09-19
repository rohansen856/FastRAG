"""An ingest that already holds an embedder must not load a second copy of the models."""

from __future__ import annotations

import pytest

from fastrag import jobs
from fastrag.config import Settings


def test_builder_reuses_the_callers_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both ingest scripts loaded the pair twice: 7.5 GB peak for a 3.7 GB model set."""

    def reload(settings: Settings) -> object:
        raise AssertionError("models were loaded a second time")

    monkeypatch.setattr(jobs, "build_embedder_and_reranker", reload)
    embedder = object()
    builder = jobs.build_index_builder(
        Settings(qdrant_url="http://localhost:6333"), registry=object(), embedder=embedder
    )
    assert builder._embedder is embedder  # noqa: SLF001
