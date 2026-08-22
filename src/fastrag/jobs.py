from __future__ import annotations

import asyncio

from .bootstrap import build_embedder_and_reranker, embedding_fingerprint
from .config import Settings
from .documents import SUPPORTED_SUFFIXES
from .indexing import IndexBuilder
from .model_artifacts import verify_configured_models
from .registry import PostgresIndexRegistry


def rebuild_documents() -> dict[str, str]:
    return asyncio.run(_rebuild_documents())


def build_index_builder(settings: Settings, registry: PostgresIndexRegistry) -> IndexBuilder:
    embedder, _ = build_embedder_and_reranker(settings)
    return IndexBuilder(
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=(
            settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        ),
        alias=settings.qdrant_alias,
        dimension=settings.active_dense_dimension,
        embedder=embedder,
        embedding_fingerprint=embedding_fingerprint(settings),
        registry=registry,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        strategies=settings.chunk_strategy_list or ("sentence",),
    )


async def _rebuild_documents() -> dict[str, str]:
    settings = Settings()
    verify_configured_models(settings)
    document_dir = settings.data_dir / "documents"
    paths = [
        path
        for path in document_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES
    ]
    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    builder = build_index_builder(settings, registry)
    manifest = await builder.rebuild(paths)
    return {"index_version": manifest.index_version, "content_version": manifest.content_version}
