from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from ..domain import Chunk, RankedChunk


class QdrantHybridRetriever:
    DENSE_VECTOR = "dense"
    SPARSE_VECTOR = "bm25"

    def __init__(
        self,
        url: str,
        collection: str,
        *,
        api_key: str | None = None,
        collection_provider: Callable[[], Awaitable[str]] | None = None,
    ) -> None:
        from fastembed import SparseTextEmbedding
        from qdrant_client import QdrantClient

        self._client: Any = QdrantClient(url=url, api_key=api_key)
        self._collection = collection
        self._collection_provider = collection_provider
        self._sparse: Any = SparseTextEmbedding(model_name="Qdrant/bm25")

    async def retrieve(
        self,
        query: str,
        vector: list[float],
        limit: int,
        *,
        collection: str | None = None,
    ) -> list[Chunk]:
        selected_collection = collection or (
            await self._collection_provider()
            if self._collection_provider is not None
            else self._collection
        )
        return await asyncio.to_thread(
            self._retrieve_sync, selected_collection, query, vector, limit
        )

    def _retrieve_sync(
        self, collection: str, query: str, vector: list[float], limit: int
    ) -> list[Chunk]:
        from qdrant_client import models

        sparse = next(iter(self._sparse.query_embed(query)))
        response = self._client.query_points(
            collection_name=collection,
            prefetch=[
                models.Prefetch(query=vector, using=self.DENSE_VECTOR, limit=limit),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse.indices.tolist(), values=sparse.values.tolist()
                    ),
                    using=self.SPARSE_VECTOR,
                    limit=limit,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        return [self._to_chunk(point) for point in response.points]

    @staticmethod
    def _to_chunk(point: Any) -> Chunk:
        payload = point.payload or {}
        return Chunk(
            chunk_id=str(payload.get("chunk_id", point.id)),
            document_id=str(payload["document_id"]),
            text=str(payload["text"]),
            title=str(payload.get("title", payload["document_id"])),
            source_uri=str(payload.get("source_uri", "")),
            page=int(payload["page"]) if payload.get("page") is not None else None,
            score=float(point.score),
            metadata=dict(payload),
        )


class FastEmbedReranker:
    def __init__(self, model_id: str, *, model_path: Path | None = None) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        self._model: Any = TextCrossEncoder(
            model_name=model_id,
            specific_model_path=str(model_path) if model_path else None,
            local_files_only=model_path is not None,
        )

    async def rerank(
        self, query: str, candidates: Sequence[Chunk], limit: int
    ) -> list[RankedChunk]:
        scores = await asyncio.to_thread(
            lambda: list(self._model.rerank(query, [chunk.text for chunk in candidates]))
        )
        ranked = sorted(
            (
                RankedChunk(chunk=chunk, score=float(score))
                for chunk, score in zip(candidates, scores, strict=True)
            ),
            key=lambda item: item.score,
            reverse=True,
        )
        return ranked[:limit]
