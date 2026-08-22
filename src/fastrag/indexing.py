from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from .adapters.retrieval import connect_qdrant
from .bootstrap import CENTROID_PATH
from .chunking import SourceDocument, build_strategy, chunk_document
from .fingerprint import EmbeddingFingerprint
from .guardrails import corpus_centroid
from .ports import Embedder
from .registry import IndexManifest, PostgresIndexRegistry


class IndexBuildError(RuntimeError):
    pass


class IndexBuilder:
    def __init__(
        self,
        *,
        qdrant_url: str,
        qdrant_api_key: str | None,
        alias: str,
        dimension: int,
        embedder: Embedder,
        embedding_fingerprint: EmbeddingFingerprint,
        registry: PostgresIndexRegistry,
        chunk_size: int = 400,
        chunk_overlap: int = 50,
        strategies: Sequence[str] = ("sentence",),
        batch_size: int = 24,
    ) -> None:
        from fastembed import SparseTextEmbedding

        self._client: Any = connect_qdrant(qdrant_url, qdrant_api_key)
        self._sparse: Any = SparseTextEmbedding(model_name="Qdrant/bm25")
        self._alias = alias
        self._dimension = dimension
        self._embedder = embedder
        self._fingerprint = embedding_fingerprint
        self._registry = registry
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap
        self._strategy_names = tuple(strategies)
        self._batch_size = batch_size

    def _strategies(self) -> list[Any]:
        return [
            build_strategy(
                name,
                embedder=self._embedder,
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )
            for name in self._strategy_names
        ]

    async def rebuild(self, paths: Sequence[Path], *, version: str | None = None) -> IndexManifest:
        files = sorted(path.resolve() for path in paths if path.is_file())
        if not files:
            raise IndexBuildError("no supported documents found")
        content_version = await asyncio.to_thread(self._content_digest, files)
        documents = await asyncio.to_thread(self._load_documents, files)
        chunks = await self._chunk(documents)
        return await self.build_from_chunks(
            chunks, content_version=content_version, version=version
        )

    async def build_from_chunks(
        self,
        chunks: Sequence[dict[str, Any]],
        *,
        content_version: str,
        version: str | None = None,
    ) -> IndexManifest:
        """Index pre-chunked payloads.

        Split out from `rebuild` so the corpus script can stream MS MARCO
        passages in without first writing them to disk, which the Render free
        tier's ephemeral filesystem could not hold anyway.
        """
        if not chunks:
            raise IndexBuildError("no chunks to index")
        index_version = version or content_version[:12]
        safe_version = re.sub(r"[^a-zA-Z0-9_-]", "-", index_version)
        collection = f"kb_{safe_version}"
        languages = sorted({str(chunk.get("language", "unknown")) for chunk in chunks})
        manifest = IndexManifest(
            index_version=index_version,
            collection_name=collection,
            content_version=content_version,
            embedding_fingerprint=self._fingerprint.digest,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            chunk_strategies=self._strategy_names,
            languages=tuple(languages),
            chunk_count=len(chunks),
        )
        await self._registry.register(manifest)
        try:
            await asyncio.to_thread(self._create_collection, collection)
            vectors = await self._upload(collection, chunks)
            await asyncio.to_thread(self._validate_collection, collection, len(chunks))
            await self._registry.mark_validated(index_version)
            await asyncio.to_thread(self._activate_alias, collection)
            await self._registry.activate(index_version)
            self._write_centroid(vectors)
            if vectors:
                await self._registry.store_centroid(index_version, corpus_centroid(vectors))
        except Exception:
            await self._registry.mark_failed(index_version)
            raise
        return replace(manifest, state="active")

    async def _chunk(self, documents: Sequence[SourceDocument]) -> list[dict[str, Any]]:
        strategies = self._strategies()
        chunks: list[dict[str, Any]] = []
        for document in documents:
            chunks.extend(await chunk_document(document, strategies))
        if not chunks:
            raise IndexBuildError("documents produced no text chunks; OCR may be required")
        return chunks

    @staticmethod
    def _load_documents(files: Sequence[Path]) -> list[SourceDocument]:
        from llama_index.core import SimpleDirectoryReader

        loaded = SimpleDirectoryReader(input_files=[str(path) for path in files]).load_data()
        documents: list[SourceDocument] = []
        for item in loaded:
            metadata = dict(item.metadata)
            source = str(metadata.get("file_path") or metadata.get("file_name") or "unknown")
            text = item.text.strip()
            if not text:
                continue
            page_value = metadata.get("page_label") or metadata.get("page_number")
            try:
                page = int(page_value) if page_value is not None else None
            except (TypeError, ValueError):
                page = None
            documents.append(
                SourceDocument(
                    document_id=hashlib.sha256(source.encode()).hexdigest()[:24],
                    text=text,
                    title=str(metadata.get("file_name") or Path(source).name),
                    source_uri=source,
                    page=page,
                    metadata=metadata,
                )
            )
        return documents

    def _create_collection(self, collection: str) -> None:
        from qdrant_client import models

        if self._client.collection_exists(collection):
            # A failed previous attempt of the same content version leaves an
            # empty-or-partial collection; drop it so ingest can be retried.
            self._client.delete_collection(collection)
        self._client.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": models.VectorParams(size=self._dimension, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=200),
            on_disk_payload=True,
        )
        # Strategy and language are filtered on every query, so they need
        # payload indexes or Qdrant falls back to a full scan.
        for field in ("strategy", "language", "document_id"):
            self._client.create_payload_index(
                collection_name=collection,
                field_name=field,
                field_schema=models.PayloadSchemaType.KEYWORD,
            )

    async def _upload(self, collection: str, chunks: Sequence[dict[str, Any]]) -> list[list[float]]:
        from qdrant_client import models

        all_vectors: list[list[float]] = []
        for offset in range(0, len(chunks), self._batch_size):
            batch = list(chunks[offset : offset + self._batch_size])
            texts = [item["text"] for item in batch]
            dense = await self._embedder.embed_documents(texts)
            sparse = await asyncio.to_thread(self._sparse_documents, texts)
            all_vectors.extend(dense)
            points = [
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
                for item, dense_vector, sparse_vector in zip(batch, dense, sparse, strict=True)
            ]
            await asyncio.to_thread(
                self._client.upsert,
                collection_name=collection,
                points=points,
                wait=True,
            )
        return all_vectors

    @staticmethod
    def _write_centroid(vectors: Sequence[Sequence[float]], path: Path = CENTROID_PATH) -> None:
        """Persist the corpus centroid used by the off-topic guardrail."""
        if not vectors:
            return
        centroid = corpus_centroid(vectors)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"centroid": centroid, "threshold": None}))

    def _sparse_documents(self, texts: list[str]) -> list[Any]:
        return list(self._sparse.passage_embed(texts))

    def _validate_collection(self, collection: str, expected: int) -> None:
        count = self._client.count(collection_name=collection, exact=True).count
        if count != expected:
            raise IndexBuildError(f"indexed {count} points; expected {expected}")

    def _activate_alias(self, collection: str) -> None:
        from qdrant_client import models

        aliases = self._client.get_aliases().aliases
        operations: list[Any] = []
        if any(alias.alias_name == self._alias for alias in aliases):
            operations.append(
                models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=self._alias))
            )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(collection_name=collection, alias_name=self._alias)
            )
        )
        self._client.update_collection_aliases(change_aliases_operations=operations)

    @staticmethod
    def _content_digest(files: Sequence[Path]) -> str:
        digest = hashlib.sha256()
        for path in files:
            digest.update(path.name.encode())
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
        return digest.hexdigest()
