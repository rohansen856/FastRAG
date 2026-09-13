"""Asymmetric embedders (E5) need a prefix on passages as well as on queries."""

from __future__ import annotations

import pytest

from fastrag.adapters.embedding import FastEmbedder
from fastrag.bootstrap import embedding_fingerprint
from fastrag.config import Settings


class _EchoModel:
    """Records the exact strings each side of the embedder sends to the model."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.passages: list[str] = []

    def query_embed(self, texts: list[str]):
        self.queries.extend(texts)
        return [[1.0, 0.0] for _ in texts]

    def passage_embed(self, texts: list[str]):
        self.passages.extend(texts)
        return [[0.0, 1.0] for _ in texts]


def _embedder(model: _EchoModel, **prefixes: str) -> FastEmbedder:
    embedder = FastEmbedder.__new__(FastEmbedder)
    embedder._model = model  # type: ignore[attr-defined]
    embedder._query_prefix = prefixes.get("query_prefix", "")  # type: ignore[attr-defined]
    embedder._document_prefix = prefixes.get("document_prefix", "")  # type: ignore[attr-defined]
    embedder._normalize = True  # type: ignore[attr-defined]
    return embedder


@pytest.mark.asyncio
async def test_prefixes_are_applied_to_their_own_side_only() -> None:
    model = _EchoModel()
    embedder = _embedder(model, query_prefix="query: ", document_prefix="passage: ")
    await embedder.embed_query("how does CRAG work")
    await embedder.embed_documents(["CRAG grades retrieval."])
    assert model.queries == ["query: how does CRAG work"]
    assert model.passages == ["passage: CRAG grades retrieval."]


def test_document_prefix_is_part_of_the_embedding_fingerprint() -> None:
    """An index built with a passage prefix must not serve queries built without one."""
    common = dict(embedding_provider="fastembed", dense_query_prefix="query: ")
    plain = embedding_fingerprint(Settings(dense_document_prefix="", **common))
    prefixed = embedding_fingerprint(Settings(dense_document_prefix="passage: ", **common))
    assert plain.document_prefix == ""
    assert prefixed.document_prefix == "passage: "
    assert plain.digest != prefixed.digest


def test_hosted_embedders_ignore_textual_prefixes() -> None:
    settings = Settings(embedding_provider="jina", dense_document_prefix="passage: ")
    assert embedding_fingerprint(settings).document_prefix == ""


@pytest.mark.parametrize("raw", ["query: ", "query:", " query:  "])
def test_prefix_whitespace_survives_env_var_trimming(raw: str) -> None:
    """Dashboards trim values; a trimmed prefix must not silently change the fingerprint."""
    assert Settings(dense_query_prefix=raw).dense_query_prefix == "query: "


def test_empty_prefix_stays_empty_and_bge_default_is_unchanged() -> None:
    assert Settings(dense_document_prefix="  ").dense_document_prefix == ""
    bge = "Represent this sentence for searching relevant passages: "
    assert Settings(dense_query_prefix=bge).dense_query_prefix == bge
