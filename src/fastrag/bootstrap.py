from __future__ import annotations

import hashlib

from .adapters.cache import RedisAnswerCache
from .adapters.embedding import FastEmbedder
from .adapters.generation import OpenAICompatibleGenerator
from .adapters.retrieval import FastEmbedReranker, QdrantHybridRetriever
from .calibration import Calibration
from .config import Settings
from .fingerprint import EmbeddingFingerprint
from .model_artifacts import verify_configured_models
from .pipeline import PipelineConfig, QueryPipeline
from .registry import PostgresIndexRegistry


def reranker_fingerprint(model_id: str, revision: str, artifact_sha256: str) -> str:
    return hashlib.sha256(f"{model_id}@{revision}:{artifact_sha256}".encode()).hexdigest()


async def build_pipeline(settings: Settings) -> tuple[QueryPipeline, RedisAnswerCache]:
    embedding = EmbeddingFingerprint(
        model_id=settings.dense_model_id,
        revision=settings.dense_model_revision,
        artifact_sha256=settings.dense_model_sha256,
        dimension=settings.dense_dimension,
        normalize=settings.dense_normalize,
        query_prefix=settings.dense_query_prefix,
    )
    verify_configured_models(settings)
    reranker_digest = reranker_fingerprint(
        settings.reranker_model_id,
        settings.reranker_revision,
        settings.reranker_sha256,
    )
    calibration = Calibration.load(settings.calibration_path)
    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    await registry.assert_embedding_fingerprint(embedding.digest)
    cache = RedisAnswerCache(
        settings.redis_url,
        embedding_fingerprint=embedding.digest,
        dimension=settings.dense_dimension,
        ttl_seconds=settings.cache_ttl_seconds,
        distance_threshold=(
            settings.cache_distance_threshold
            if settings.cache_distance_threshold is not None
            else calibration.cache_distance_threshold
        ),
    )
    await cache.initialize()
    pipeline = QueryPipeline(
        embedder=FastEmbedder(
            settings.dense_model_id,
            query_prefix=settings.dense_query_prefix,
            normalize=settings.dense_normalize,
            model_path=settings.dense_model_path,
        ),
        retriever=QdrantHybridRetriever(
            settings.qdrant_url,
            settings.qdrant_alias,
            api_key=(
                settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
            ),
        ),
        reranker=FastEmbedReranker(
            settings.reranker_model_id, model_path=settings.reranker_model_path
        ),
        generator=OpenAICompatibleGenerator(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value(),
            model=settings.llm_model,
            system_prompt=settings.prompt_path.read_text(),
            max_tokens=settings.max_answer_tokens,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
        cache=cache,
        calibration=calibration,
        index_provider=registry.active_snapshot,
        config=PipelineConfig(
            embedding_fingerprint=embedding.digest,
            reranker_fingerprint=reranker_digest,
            prompt_version=settings.prompt_version,
            generator_model=settings.llm_model,
            max_answer_tokens=settings.max_answer_tokens,
            candidate_k=settings.retrieval_candidate_k,
            context_top_k=settings.context_top_k,
            max_context_tokens=settings.max_context_tokens,
            content_version=settings.content_version,
        ),
    )
    return pipeline, cache
