from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from typing import Any

from . import observability
from .adapters.cache import RedisAnswerCache
from .adapters.generation import FallbackGenerator, OpenAICompatibleGenerator
from .calibration import Calibration
from .config import Settings
from .crag import CorrectiveRetrieval
from .fingerprint import EmbeddingFingerprint
from .guardrails import Guardrails
from .harness import harness_from_settings
from .model_artifacts import verify_configured_models
from .pipeline import PipelineConfig, QueryPipeline
from .ports import Transcriber
from .registry import PostgresIndexRegistry

CENTROID_PATH = Path("config/corpus_centroid.json")


def reranker_fingerprint(model_id: str, revision: str, artifact_sha256: str) -> str:
    return hashlib.sha256(f"{model_id}@{revision}:{artifact_sha256}".encode()).hexdigest()


def embedding_fingerprint(settings: Settings) -> EmbeddingFingerprint:
    return EmbeddingFingerprint(
        model_id=settings.active_dense_model_id,
        revision=settings.active_dense_revision,
        artifact_sha256=settings.active_dense_artifact,
        dimension=settings.active_dense_dimension,
        normalize=settings.dense_normalize,
        query_prefix=settings.active_dense_query_prefix,
    )


def build_embedder_and_reranker(settings: Settings) -> tuple[Any, Any]:
    """Pick in-process ONNX models or hosted APIs based on the active profile."""
    embedder: Any
    reranker: Any
    if settings.active_embedding_provider == "jina" and settings.active_reranker_provider == "jina":
        from .adapters.jina import build_jina_pair

        if settings.jina_api_key is None:
            raise ValueError("FASTRAG_JINA_API_KEY is required for the jina provider")
        # One HTTP client and one circuit breaker across both endpoints.
        return build_jina_pair(
            api_key=settings.jina_api_key.get_secret_value(),
            base_url=settings.jina_base_url,
            embedding_model=settings.jina_embedding_model,
            embedding_dimension=settings.jina_embedding_dimension,
            reranker_model=settings.jina_reranker_model,
            timeout_seconds=settings.jina_timeout_seconds,
            harness=harness_from_settings("jina", settings),
        )

    if settings.active_embedding_provider == "jina":
        from .adapters.jina import JinaEmbedder

        if settings.jina_api_key is None:
            raise ValueError("FASTRAG_JINA_API_KEY is required for the jina provider")
        embedder = JinaEmbedder(
            api_key=settings.jina_api_key.get_secret_value(),
            model=settings.jina_embedding_model,
            dimension=settings.jina_embedding_dimension,
            base_url=settings.jina_base_url,
            timeout_seconds=settings.jina_timeout_seconds,
            normalize=settings.dense_normalize,
            harness=harness_from_settings("jina", settings),
        )
    else:
        from .adapters.embedding import FastEmbedder

        embedder = FastEmbedder(
            settings.dense_model_id,
            query_prefix=settings.dense_query_prefix,
            normalize=settings.dense_normalize,
            model_path=settings.dense_model_path,
        )

    if settings.active_reranker_provider == "jina":
        from .adapters.jina import JinaReranker

        if settings.jina_api_key is None:
            raise ValueError("FASTRAG_JINA_API_KEY is required for the jina provider")
        reranker = JinaReranker(
            api_key=settings.jina_api_key.get_secret_value(),
            model=settings.jina_reranker_model,
            base_url=settings.jina_base_url,
            timeout_seconds=settings.jina_timeout_seconds,
            harness=harness_from_settings("jina", settings),
        )
    else:
        from .adapters.retrieval import FastEmbedReranker

        reranker = FastEmbedReranker(
            settings.reranker_model_id, model_path=settings.reranker_model_path
        )
    return embedder, reranker


def build_retriever(settings: Settings) -> Any:
    from .adapters.retrieval import QdrantHybridRetriever

    return QdrantHybridRetriever(
        settings.qdrant_url,
        settings.qdrant_alias,
        api_key=(settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None),
        leg_k=settings.retrieval_leg_k,
        sparse=settings.sparse_retrieval_enabled,
    )


def build_generator(settings: Settings) -> Any:
    primary = OpenAICompatibleGenerator(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        system_prompt=settings.prompt_path.read_text(),
        max_tokens=settings.max_answer_tokens,
        timeout_seconds=settings.effective_llm_timeout_seconds,
        harness=harness_from_settings("generator", settings),
        provider_name="generator",
    )
    if not (settings.llm_fallback_base_url and settings.llm_fallback_model):
        return primary
    secondary = OpenAICompatibleGenerator(
        base_url=settings.llm_fallback_base_url,
        api_key=(
            settings.llm_fallback_api_key.get_secret_value()
            if settings.llm_fallback_api_key
            else settings.llm_api_key.get_secret_value()
        ),
        model=settings.llm_fallback_model,
        system_prompt=settings.prompt_path.read_text(),
        max_tokens=settings.max_answer_tokens,
        timeout_seconds=settings.effective_llm_timeout_seconds,
        harness=harness_from_settings("generator-fallback", settings),
        provider_name="generator-fallback",
    )
    return FallbackGenerator(primary, secondary)


def build_transcriber(settings: Settings) -> Transcriber | None:
    provider = settings.active_stt_provider
    if provider == "sarvam":
        from .adapters.stt import SarvamTranscriber

        if settings.sarvam_api_key is None:
            return None
        return SarvamTranscriber(
            api_key=settings.sarvam_api_key.get_secret_value(),
            base_url=settings.sarvam_base_url,
            model=settings.sarvam_model,
            mode=settings.sarvam_mode,
            timeout_seconds=settings.stt_timeout_seconds,
            harness=harness_from_settings("sarvam", settings),
        )
    if provider == "elevenlabs":
        from .adapters.stt import ElevenLabsTranscriber

        if settings.elevenlabs_api_key is None:
            return None
        return ElevenLabsTranscriber(
            api_key=settings.elevenlabs_api_key.get_secret_value(),
            base_url=settings.elevenlabs_base_url,
            model=settings.elevenlabs_model,
            timeout_seconds=settings.stt_timeout_seconds,
            harness=harness_from_settings("elevenlabs", settings),
        )
    return None


def load_corpus_centroid(path: Path = CENTROID_PATH) -> tuple[list[float] | None, float | None]:
    """Load the off-topic reference vector produced during ingestion."""
    if not path.is_file():
        return None, None
    try:
        payload = json.loads(path.read_text())
        centroid = [float(value) for value in payload["centroid"]]
        threshold = float(payload["threshold"]) if payload.get("threshold") is not None else None
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, None
    return centroid, threshold


async def build_pipeline(settings: Settings) -> tuple[QueryPipeline, RedisAnswerCache]:
    observability.configure(settings)
    embedding = embedding_fingerprint(settings)
    verify_configured_models(settings)
    reranker_digest = reranker_fingerprint(
        settings.active_reranker_model_id,
        settings.active_reranker_revision,
        settings.active_reranker_artifact,
    )
    calibration = Calibration.load(
        settings.calibration_path, raw_json=settings.calibration_json
    )
    registry = PostgresIndexRegistry(settings.database_url)
    await registry.initialize()
    await registry.assert_embedding_fingerprint(embedding.digest)

    cache = RedisAnswerCache(
        settings.redis_url,
        embedding_fingerprint=embedding.digest,
        dimension=settings.active_dense_dimension,
        ttl_seconds=settings.cache_ttl_seconds,
        distance_threshold=(
            settings.cache_distance_threshold
            if settings.cache_distance_threshold is not None
            else calibration.cache_distance_threshold
        ),
        semantic_enabled=settings.semantic_cache_enabled,
    )
    await cache.initialize()

    embedder, reranker = build_embedder_and_reranker(settings)
    generator = build_generator(settings)

    retriever = build_retriever(settings)

    centroid, centroid_threshold = load_corpus_centroid()
    if centroid is None:
        centroid = await asyncio.to_thread(registry.centroid_from_active)
    guardrails = Guardrails(
        enabled=settings.guardrails_enabled,
        languages=settings.guardrail_language_set,
        corpus_centroid=centroid,
        offtopic_threshold=(
            calibration.offtopic_threshold
            if calibration.offtopic_threshold is not None
            else centroid_threshold
        ),
        safety_generator=generator,
    )
    crag = CorrectiveRetrieval(
        calibration=calibration,
        reranker=reranker,
        retriever=retriever,
        embedder=embedder,
        generator=generator,
        enabled=settings.crag_enabled,
        max_rewrites=settings.crag_max_rewrites,
        strip_min_tokens=settings.crag_strip_min_tokens,
        candidate_k=settings.retrieval_candidate_k,
    )

    strategies = settings.chunk_strategy_list
    pipeline = QueryPipeline(
        embedder=embedder,
        retriever=retriever,
        reranker=reranker,
        generator=generator,
        cache=cache,
        calibration=calibration,
        index_provider=registry.active_snapshot,
        guardrails=guardrails,
        crag=crag,
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
            chunk_strategy=strategies[0] if strategies else "sentence",
            deadline_seconds=settings.effective_request_deadline_seconds,
        ),
    )
    return pipeline, cache
