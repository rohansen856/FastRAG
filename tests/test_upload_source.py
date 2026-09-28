"""Uploaded documents cite the file the caller sent, not the server's temp copy."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from conftest import FakeEmbedder

from fastrag.config import Settings
from fastrag.ingest_document import DocumentIngester


class _Registry:
    async def initialize(self) -> None:
        return None

    async def active_snapshot(self) -> Any:
        return SimpleNamespace(collection_name="kb")


def _ingester() -> tuple[DocumentIngester, list[dict[str, Any]]]:
    ingester = DocumentIngester.__new__(DocumentIngester)
    ingester._settings = Settings()  # type: ignore[attr-defined]
    ingester._registry = _Registry()  # type: ignore[attr-defined]
    ingester._embedder = FakeEmbedder()  # type: ignore[attr-defined]
    upserted: list[dict[str, Any]] = []

    async def upsert(collection: str, chunks: list[dict[str, Any]]) -> None:
        upserted.extend(chunks)

    ingester._ensure_payload_indexes = lambda collection: None  # type: ignore[method-assign]
    ingester._upsert_chunks = upsert  # type: ignore[method-assign]
    return ingester, upserted


@pytest.mark.asyncio
async def test_upload_cites_the_uploaded_filename() -> None:
    ingester, upserted = _ingester()
    await ingester.ingest_upload(
        filename="notes/orchard.txt",
        payload=b"The quince trees were pruned by Idris on the fourth of March.",
    )
    assert upserted
    assert {chunk["source_uri"] for chunk in upserted} == {"orchard.txt"}
