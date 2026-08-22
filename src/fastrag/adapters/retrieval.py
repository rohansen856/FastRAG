from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

from ..domain import Chunk, RankedChunk


def connect_qdrant(url: str, api_key: str | None = None) -> Any:
    """Open a Qdrant client, including Cloud hosts whose REST port is 443.

    `QdrantClient` defaults to 6333 even for `https://host` URLs with no port.
    Qdrant Cloud's REST endpoint is on 443, and 6333 times out from most networks.
    """
    from qdrant_client import QdrantClient

    kwargs: dict[str, Any] = {"url": url, "api_key": api_key, "timeout": 60}
    host = url.split("://", 1)[-1].split("/", 1)[0]
    if url.startswith("https://") and ":" not in host:
        kwargs["port"] = 443
    return QdrantClient(**kwargs)


class QdrantHybridRetriever:
    """Dense + BM25 sparse retrieval fused with reciprocal rank fusion.

    Each retrieval leg pulls `leg_k` candidates so fusion has enough material to
    reorder; only `limit` survive fusion and go on to the reranker.
    """

    DENSE_VECTOR = "dense"
    SPARSE_VECTOR = "bm25"

    def __init__(
        self,
        url: str,
        collection: str,
        *,
        api_key: str | None = None,
        collection_provider: Callable[[], Awaitable[str]] | None = None,
        leg_k: int = 40,
        sparse: bool = True,
    ) -> None:
        self._client: Any = connect_qdrant(url, api_key)
        self._collection = collection
        self._collection_provider = collection_provider
        self._leg_k = leg_k
        self._sparse: Any = None
        if sparse:
            # Importing fastembed pulls in onnxruntime, which is a meaningful
            # slice of a 512 MB instance. Hosts that cannot afford it fall back
            # to dense-only retrieval by disabling sparse.
            from fastembed import SparseTextEmbedding

            self._sparse = SparseTextEmbedding(model_name="Qdrant/bm25")

    async def retrieve(
        self,
        query: str,
        vector: list[float],
        limit: int,
        *,
        collection: str | None = None,
        strategy: str | None = None,
        language: str | None = None,
        document_ids: list[str] | None = None,
        deadline: object = None,
    ) -> list[Chunk]:
        selected_collection = collection or (
            await self._collection_provider()
            if self._collection_provider is not None
            else self._collection
        )
        return await asyncio.to_thread(
            self._retrieve_sync,
            selected_collection,
            query,
            vector,
            limit,
            strategy,
            language,
            document_ids,
        )

    def _retrieve_sync(
        self,
        collection: str,
        query: str,
        vector: list[float],
        limit: int,
        strategy: str | None,
        language: str | None,
        document_ids: list[str] | None,
    ) -> list[Chunk]:
        from qdrant_client import models

        leg_k = max(self._leg_k, limit)
        conditions: list[Any] = []
        if strategy:
            conditions.append(
                models.FieldCondition(key="strategy", match=models.MatchValue(value=strategy))
            )
        if language:
            conditions.append(
                models.FieldCondition(key="language", match=models.MatchValue(value=language))
            )
        if document_ids:
            conditions.append(
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchAny(any=document_ids),
                )
            )
        must_not: list[Any] = []
        if not document_ids:
            # Session uploads share the active collection but must not pollute corpus search.
            must_not.append(
                models.FieldCondition(
                    key="session_upload",
                    match=models.MatchValue(value=True),
                )
            )
        query_filter = (
            models.Filter(must=conditions, must_not=must_not)
            if conditions or must_not
            else None
        )

        if self._sparse is None:
            response = self._client.query_points(
                collection_name=collection,
                query=vector,
                using=self.DENSE_VECTOR,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
            return [self._to_chunk(point) for point in response.points]

        sparse = next(iter(self._sparse.query_embed(query)))
        response = self._client.query_points(
            collection_name=collection,
            prefetch=[
                models.Prefetch(
                    query=vector,
                    using=self.DENSE_VECTOR,
                    limit=leg_k,
                    filter=query_filter,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse.indices.tolist(), values=sparse.values.tolist()
                    ),
                    using=self.SPARSE_VECTOR,
                    limit=leg_k,
                    filter=query_filter,
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
        self,
        query: str,
        candidates: Sequence[Chunk],
        limit: int,
        *,
        deadline: object = None,
    ) -> list[RankedChunk]:
        if not candidates:
            return []
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

    async def score(self, query: str, texts: Sequence[str]) -> list[float]:
        """Raw relevance scores, used by CRAG strip refinement."""
        if not texts:
            return []
        scores = await asyncio.to_thread(lambda: list(self._model.rerank(query, list(texts))))
        return [float(score) for score in scores]
