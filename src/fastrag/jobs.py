from __future__ import annotations

import asyncio

from .adapters.embedding import FastEmbedder
from .config import Settings
from .fingerprint import EmbeddingFingerprint
from .indexing import IndexBuilder
from .model_artifacts import verify_configured_models
from .registry import PostgresIndexRegistry

SUPPORTED_SUFFIXES = {".pdf", ".md", ".markdown", ".txt"}


def rebuild_documents() -> dict[str, str]:
    return asyncio.run(_rebuild_documents())


async def _rebuild_documents() -> dict[str, str]:
    settings = Settings()
    verify_configured_models(settings)
    document_dir = settings.data_dir / "documents"
    paths = [
        path
        for path in document_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in SUPPORTED_SUFFIXES
    ]
    fingerprint = EmbeddingFingerprint(
        model_id=settings.dense_model_id,
        revision=settings.dense_model_revision,
        artifact_sha256=settings.dense_model_sha256,
        dimension=settings.dense_dimension,
        normalize=settings.dense_normalize,
        query_prefix=settings.dense_query_prefix,
    )
    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    builder = IndexBuilder(
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=(
            settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        ),
        alias=settings.qdrant_alias,
        dimension=settings.dense_dimension,
        embedder=FastEmbedder(
            settings.dense_model_id,
            query_prefix=settings.dense_query_prefix,
            normalize=settings.dense_normalize,
            model_path=settings.dense_model_path,
        ),
        embedding_fingerprint=fingerprint,
        registry=registry,
    )
    manifest = await builder.rebuild(paths)
    return {"index_version": manifest.index_version, "content_version": manifest.content_version}
