from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.schema import MetadataMode

from .fingerprint import EmbeddingFingerprint
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
    ) -> None:
        from fastembed import SparseTextEmbedding
        from qdrant_client import QdrantClient

        self._client: Any = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self._sparse: Any = SparseTextEmbedding(model_name="Qdrant/bm25")
        self._alias = alias
        self._dimension = dimension
        self._embedder = embedder
        self._fingerprint = embedding_fingerprint
        self._registry = registry
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def rebuild(self, paths: Sequence[Path], *, version: str | None = None) -> IndexManifest:
        files = sorted(path.resolve() for path in paths if path.is_file())
        if not files:
            raise IndexBuildError("no supported documents found")
        content_version = await asyncio.to_thread(self._content_digest, files)
        index_version = version or content_version[:12]
        safe_version = re.sub(r"[^a-zA-Z0-9_-]", "-", index_version)
        collection = f"kb_{safe_version}"
        manifest = IndexManifest(
            index_version=index_version,
            collection_name=collection,
            content_version=content_version,
            embedding_fingerprint=self._fingerprint.digest,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
        )
        await self._registry.register(manifest)
        try:
            chunks = await asyncio.to_thread(self._load_and_chunk, files)
            await asyncio.to_thread(self._create_collection, collection)
            await self._upload(collection, chunks)
            await asyncio.to_thread(self._validate_collection, collection, len(chunks))
            await self._registry.mark_validated(index_version)
            await asyncio.to_thread(self._activate_alias, collection)
            await self._registry.activate(index_version)
        except Exception:
            await self._registry.mark_failed(index_version)
            raise
        return replace(manifest, state="active")

    def _load_and_chunk(self, files: Sequence[Path]) -> list[dict[str, Any]]:
        documents = SimpleDirectoryReader(input_files=[str(path) for path in files]).load_data()
        splitter = SentenceSplitter(
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            include_metadata=True,
        )
        nodes = splitter.get_nodes_from_documents(documents)
        chunks: list[dict[str, Any]] = []
        for node in nodes:
            metadata = dict(node.metadata)
            source = str(metadata.get("file_path") or metadata.get("file_name") or "unknown")
            document_id = hashlib.sha256(source.encode()).hexdigest()[:24]
            text = node.get_content(metadata_mode=MetadataMode.NONE).strip()
            if not text:
                continue
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{text}"))
            page_value = metadata.get("page_label") or metadata.get("page_number")
            try:
                page = int(page_value) if page_value is not None else None
            except (TypeError, ValueError):
                page = None
            chunks.append(
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "text": text,
                    "title": str(metadata.get("file_name") or Path(source).name),
                    "source_uri": source,
                    "page": page,
                }
            )
        if not chunks:
            raise IndexBuildError("documents produced no text chunks; OCR may be required")
        return chunks

    def _create_collection(self, collection: str) -> None:
        from qdrant_client import models

        if self._client.collection_exists(collection):
            raise IndexBuildError(f"collection already exists: {collection}")
        self._client.create_collection(
            collection_name=collection,
            vectors_config={
                "dense": models.VectorParams(size=self._dimension, distance=models.Distance.COSINE)
            },
            sparse_vectors_config={"bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)},
            hnsw_config=models.HnswConfigDiff(m=16, ef_construct=200),
            on_disk_payload=True,
        )

    async def _upload(self, collection: str, chunks: Sequence[dict[str, Any]]) -> None:
        from qdrant_client import models

        batch_size = 64
        for offset in range(0, len(chunks), batch_size):
            batch = list(chunks[offset : offset + batch_size])
            texts = [item["text"] for item in batch]
            dense = await self._embedder.embed_documents(texts)
            sparse = await asyncio.to_thread(self._sparse_documents, texts)
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
