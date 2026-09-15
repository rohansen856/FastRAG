"""In-process models can be placed on an execution provider and batched explicitly."""

from __future__ import annotations

import pytest

from fastrag.adapters.embedding import FastEmbedder
from fastrag.adapters.retrieval import FastEmbedReranker
from fastrag.config import Settings
from fastrag.domain import Chunk


class _Recorder:
    """Stands in for a FastEmbed model class and records how it was built and called."""

    built: dict[str, object] = {}
    rerank_batches: list[object] = []

    def __init__(self, **kwargs: object) -> None:
        type(self).built = kwargs

    def rerank(self, query: str, documents: list[str], **kwargs: object):
        type(self).rerank_batches.append(kwargs.get("batch_size"))
        return [0.0 for _ in documents]


def test_providers_reach_the_embedding_model(monkeypatch: pytest.MonkeyPatch) -> None:
    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", _Recorder)
    FastEmbedder("model", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
    assert _Recorder.built["providers"] == ["CUDAExecutionProvider", "CPUExecutionProvider"]


def test_no_providers_keeps_fastembeds_default(monkeypatch: pytest.MonkeyPatch) -> None:
    import fastembed

    monkeypatch.setattr(fastembed, "TextEmbedding", _Recorder)
    FastEmbedder("model")
    assert "providers" not in _Recorder.built


@pytest.mark.asyncio
async def test_reranker_uses_its_configured_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    """Batching pads every pair to the longest; for long code chunks one at a time is faster."""
    import fastembed.rerank.cross_encoder as cross_encoder

    monkeypatch.setattr(cross_encoder, "TextCrossEncoder", _Recorder)
    reranker = FastEmbedReranker("model", providers=["CUDAExecutionProvider"], batch_size=1)
    assert _Recorder.built["providers"] == ["CUDAExecutionProvider"]
    chunk = Chunk(
        chunk_id="c",
        document_id="d",
        text="t",
        title="t",
        source_uri="",
        page=None,
        score=0.0,
        metadata={},
    )
    _Recorder.rerank_batches.clear()
    await reranker.rerank("q", [chunk], 1)
    await reranker.score("q", ["t"])
    assert _Recorder.rerank_batches == [1, 1]


def test_execution_settings_parse_to_lists() -> None:
    settings = Settings(
        reranker_execution_providers=" CUDAExecutionProvider , CPUExecutionProvider ",
        dense_execution_providers="",
    )
    assert settings.reranker_execution_provider_list == [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    assert settings.dense_execution_provider_list is None
