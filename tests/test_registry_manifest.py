"""A deferred build can be reloaded for activation after its centroid is stored."""

from __future__ import annotations

import json

import pytest

from fastrag.registry import IndexManifest, PostgresIndexRegistry


@pytest.mark.asyncio
async def test_manifest_reloads_with_a_stored_centroid(monkeypatch: pytest.MonkeyPatch) -> None:
    """`store_centroid` adds a key the dataclass does not declare; reloading must ignore it."""
    stored = {
        "index_version": "v1",
        "collection_name": "kb_v1",
        "content_version": "c1",
        "embedding_fingerprint": "fp",
        "chunk_size": 150,
        "chunk_overlap": 50,
        "state": "building",
        "chunk_strategies": ["sentence"],
        "languages": ["en"],
        "chunk_count": 3,
        "centroid": [0.1, 0.2],
    }
    registry = PostgresIndexRegistry("postgresql://unused")
    monkeypatch.setattr(
        registry,
        "_manifest_sync",
        lambda version: {"manifest": json.dumps(stored), "state": "validated"},
    )
    manifest = await registry.manifest("v1")
    assert manifest == IndexManifest(
        index_version="v1",
        collection_name="kb_v1",
        content_version="c1",
        embedding_fingerprint="fp",
        chunk_size=150,
        chunk_overlap=50,
        state="validated",
        chunk_strategies=("sentence",),
        languages=("en",),
        chunk_count=3,
    )
