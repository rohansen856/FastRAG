"""Incremental document ingest into the active Qdrant collection."""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .adapters.retrieval import connect_qdrant
from .bootstrap import build_embedder_and_reranker
from .chunking import build_strategy, chunk_document
from .config import Settings
from .documents import MAX_UPLOAD_BYTES, is_supported, parse_file, suffix_of
from .indexing import IndexBuildError
from .registry import PostgresIndexRegistry

MAX_INGEST_CHUNKS = 500
DEFAULT_INGEST_STRATEGY = "sentence"


class DocumentIngestError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class IngestResult:
    document_id: str
    title: str
    chunk_count: int
    strategy: str


class DocumentIngester:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Any = connect_qdrant(
            settings.qdrant_url,
            settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
        )
        self._registry = PostgresIndexRegistry(settings.database_url)
        self._embedder, _ = build_embedder_and_reranker(settings)
        self._sparse_enabled = settings.sparse_retrieval_enabled
        self._sparse: Any = None
        if self._sparse_enabled:
            from fastembed import SparseTextEmbedding

            self._sparse = SparseTextEmbedding(model_name="Qdrant/bm25")
        self._batch_size = 24

    async def ingest_upload(
        self,
        *,
        filename: str | None,
        payload: bytes,
        title: str | None = None,
        strategy: str = DEFAULT_INGEST_STRATEGY,
    ) -> IngestResult:
        if len(payload) > MAX_UPLOAD_BYTES:
            raise DocumentIngestError(
                f"document exceeds {MAX_UPLOAD_BYTES} bytes ({len(payload)} uploaded)"
            )
        if not is_supported(filename):
            raise DocumentIngestError(
                f"unsupported file type {suffix_of(filename)!r}; "
                f"supported: pdf, md, txt, html, json, csv, xml, yaml, rst, log, …"
            )

        document_id = f"user-{uuid.uuid4().hex[:20]}"
        display = title or Path(filename or "upload").name
        suffix = suffix_of(filename) or ".txt"

        await self._registry.initialize()
        active = await self._registry.active_snapshot()
        collection = active.collection_name

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)

        try:
            document = await asyncio.to_thread(
                parse_file, temp_path, document_id=document_id, title=display
            )
            chunk_strategy = build_strategy(
                strategy,
                embedder=self._embedder,
                chunk_size=self._settings.chunk_size,
                chunk_overlap=self._settings.chunk_overlap,
            )
            chunks = await chunk_document(document, [chunk_strategy])
            if not chunks:
                raise DocumentIngestError("document produced no text chunks; OCR may be required")
            if len(chunks) > MAX_INGEST_CHUNKS:
                raise DocumentIngestError(
                    f"document produced {len(chunks)} chunks; limit is {MAX_INGEST_CHUNKS}"
                )
            for chunk in chunks:
                chunk["session_upload"] = True
            await asyncio.to_thread(self._ensure_payload_indexes, collection)
            await self._upsert_chunks(collection, chunks)
        finally:
            await asyncio.to_thread(lambda: temp_path.unlink(missing_ok=True))

        return IngestResult(
            document_id=document_id,
            title=display,
            chunk_count=len(chunks),
            strategy=strategy,
        )

    def _ensure_payload_indexes(self, collection: str) -> None:
        from qdrant_client import models

        for field in ("strategy", "language", "document_id"):
            try:
                self._client.create_payload_index(
                    collection_name=collection,
                    field_name=field,
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
            except Exception:
                # Index may already exist on collections built after this change.
                pass
        try:
            self._client.create_payload_index(
                collection_name=collection,
                field_name="session_upload",
                field_schema=models.PayloadSchemaType.BOOL,
            )
        except Exception:
            pass

    async def _upsert_chunks(self, collection: str, chunks: list[dict[str, Any]]) -> None:
        for offset in range(0, len(chunks), self._batch_size):
            batch = chunks[offset : offset + self._batch_size]
            texts = [item["text"] for item in batch]
            dense = await self._embedder.embed_documents(texts)
            await asyncio.to_thread(
                self._upsert_batch_sync, collection, batch, dense
            )

    def _upsert_batch_sync(
        self,
        collection: str,
        batch: list[dict[str, Any]],
        dense: list[list[float]],
    ) -> None:
        from qdrant_client import models

        points: list[Any] = []
        if self._sparse_enabled and self._sparse is not None:
            sparse_vectors = list(self._sparse.passage_embed([item["text"] for item in batch]))
            for item, dense_vector, sparse_vector in zip(batch, dense, sparse_vectors, strict=True):
                points.append(
                    models.PointStruct(
                        id=item["chunk_id"],
                        vector={
                            "dense": dense_vector,
                            "bm25": models.SparseVector(
                                indices=sparse_vector.indices.tolist(),
                                values=sparse_vector.values.tolist(),
                            ),
                        },
                        payload=item,
                    )
                )
        else:
            for item, dense_vector in zip(batch, dense, strict=True):
                points.append(
                    models.PointStruct(
                        id=item["chunk_id"],
                        vector={"dense": dense_vector},
                        payload=item,
                    )
                )
        self._client.upsert(collection_name=collection, points=points, wait=True)


async def delete_user_document(settings: Settings, document_id: str) -> None:
    from .documents import is_user_document

    if not is_user_document(document_id):
        raise DocumentIngestError("only session uploads can be removed")

    client: Any = connect_qdrant(
        settings.qdrant_url,
        settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None,
    )
    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    active = await registry.active_snapshot()
    collection = active.collection_name

    from qdrant_client import models

    await asyncio.to_thread(
        client.delete,
        collection_name=collection,
        points_selector=models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id",
                        match=models.MatchValue(value=document_id),
                    )
                ]
            )
        ),
        wait=True,
    )


async def ingest_upload(
    settings: Settings,
    *,
    filename: str | None,
    payload: bytes,
    title: str | None = None,
    strategy: str = DEFAULT_INGEST_STRATEGY,
) -> IngestResult:
    ingester = DocumentIngester(settings)
    try:
        return await ingester.ingest_upload(
            filename=filename,
            payload=payload,
            title=title,
            strategy=strategy,
        )
    except (IndexBuildError, ValueError) as exc:
        raise DocumentIngestError(str(exc)) from exc
