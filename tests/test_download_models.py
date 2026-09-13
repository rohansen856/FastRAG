"""The model downloader fetches whichever models are configured, not a fixed pair."""

from __future__ import annotations

from pathlib import Path

import pytest

from fastrag import download_models


def test_downloads_the_configured_repositories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(download_models, "snapshot_download", lambda **kw: calls.append(kw))
    monkeypatch.setattr(download_models, "verify_configured_models", lambda settings: None)
    monkeypatch.setenv("FASTRAG_DENSE_MODEL_PATH", str(tmp_path / "dense"))
    monkeypatch.setenv("FASTRAG_RERANKER_MODEL_PATH", str(tmp_path / "reranker"))
    monkeypatch.setenv("FASTRAG_DENSE_MODEL_REPOSITORY", "qdrant/multilingual-e5-large-onnx")
    monkeypatch.setenv("FASTRAG_DENSE_MODEL_REVISION", "abc")
    monkeypatch.setenv(
        "FASTRAG_RERANKER_MODEL_REPOSITORY", "jinaai/jina-reranker-v2-base-multilingual"
    )

    download_models.main()

    dense, reranker = calls
    assert dense["repo_id"] == "qdrant/multilingual-e5-large-onnx"
    assert dense["revision"] == "abc"
    assert reranker["repo_id"] == "jinaai/jina-reranker-v2-base-multilingual"
    # E5 keeps its weights beside the graph; skipping them yields an unloadable model.
    assert "*.onnx_data" in dense["allow_patterns"]  # type: ignore[operator]
