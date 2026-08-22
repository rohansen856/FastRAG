from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Profile = Literal["local", "cloud"]
EmbeddingProvider = Literal["fastembed", "jina"]
RerankerProvider = Literal["fastembed", "jina"]
TranscriberProvider = Literal["sarvam", "elevenlabs", "none"]

HOSTED_REVISION = "hosted-api"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FASTRAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    release: str = "dev"
    log_level: str = "INFO"
    query_api_key: SecretStr = SecretStr("change-me-query")
    admin_api_key: SecretStr = SecretStr("change-me-admin")

    # `local` runs in-process ONNX models against local infrastructure and is the
    # profile the sub-200ms latency numbers are measured on. `cloud` runs entirely
    # on hosted free tiers and fits Render's 512 MB / 0.1 CPU free instance.
    profile: Profile = "local"
    embedding_provider: EmbeddingProvider | None = None
    reranker_provider: RerankerProvider | None = None
    stt_provider: TranscriberProvider | None = None

    qdrant_url: str = "http://qdrant:6333"
    qdrant_api_key: SecretStr | None = None
    qdrant_alias: str = "kb_current"
    redis_url: str = "redis://redis:6379/0"

    dense_model_id: str = "BAAI/bge-base-en-v1.5"
    dense_model_revision: str = "pinned-in-deployment"
    dense_model_sha256: str = "set-in-production"
    dense_model_path: Path | None = None
    dense_model_file: str = "model_optimized.onnx"
    dense_dimension: int = 768
    dense_query_prefix: str = "Represent this sentence for searching relevant passages: "
    dense_normalize: bool = True
    reranker_model_id: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    reranker_revision: str = "pinned-in-deployment"
    reranker_sha256: str = "set-in-production"
    reranker_model_path: Path | None = None
    reranker_model_file: str = "onnx/model.onnx"

    jina_api_key: SecretStr | None = None
    jina_base_url: str = "https://api.jina.ai/v1"
    jina_embedding_model: str = "jina-embeddings-v3"
    jina_embedding_dimension: int = 1024
    jina_reranker_model: str = "jina-reranker-v2-base-multilingual"
    jina_timeout_seconds: float = 15.0

    sarvam_api_key: SecretStr | None = None
    sarvam_base_url: str = "https://api.sarvam.ai"
    sarvam_model: str = "saaras:v3"
    sarvam_mode: str = "transcribe"
    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_base_url: str = "https://api.elevenlabs.io/v1"
    elevenlabs_model: str = "scribe_v1"
    stt_timeout_seconds: float = 20.0
    stt_max_bytes: int = 12 * 1024 * 1024

    # Disable to drop the fastembed/onnxruntime import and run dense-only
    # retrieval, for hosts too small to carry it.
    sparse_retrieval_enabled: bool = True
    retrieval_leg_k: int = 40
    retrieval_candidate_k: int = 20
    context_top_k: int = 5
    max_context_tokens: int = 2400
    max_answer_tokens: int = 200

    calibration_path: Path = Path("config/calibration.json")
    # Prefer this on Vercel (gitignored file is not uploaded). Paste the JSON object.
    calibration_json: str | None = None
    prompt_path: Path = Path("config/system_prompt.txt")
    prompt_version: str = "v1"

    llm_base_url: str = "http://llm-gateway:8000/v1"
    llm_api_key: SecretStr = SecretStr("not-configured")
    llm_model: str = "configured-at-deploy"
    llm_timeout_seconds: float = 20.0
    llm_fallback_base_url: str | None = None
    llm_fallback_api_key: SecretStr | None = None
    llm_fallback_model: str | None = None

    retry_max_attempts: int = 3
    retry_initial_backoff_seconds: float = 0.25
    retry_max_backoff_seconds: float = 4.0
    circuit_breaker_failures: int = 5
    circuit_breaker_reset_seconds: float = 30.0
    request_deadline_seconds: float = 25.0

    crag_enabled: bool = True
    crag_max_rewrites: int = 1
    crag_strip_min_tokens: int = 24

    guardrails_enabled: bool = True
    guardrail_offtopic_margin: float = 0.12
    guardrail_languages: str = "en,hi,bn,ta,te,mr"

    cache_ttl_seconds: int = 604_800
    cache_distance_threshold: float | None = None
    semantic_cache_enabled: bool = True
    content_version: str = "empty"

    chunk_strategies: str = "sentence"
    chunk_size: int = 400
    chunk_overlap: int = 50

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True
    trace_raw_content: bool = False

    data_dir: Path = Path("/data")
    database_url: str = "postgresql://fastrag:fastrag@postgres:5432/fastrag"
    cors_origins: str = "*"

    @field_validator("retrieval_candidate_k")
    @classmethod
    def candidate_k_must_cover_context(cls, value: int) -> int:
        if value < 1:
            raise ValueError("retrieval_candidate_k must be positive")
        return value

    @field_validator("cache_distance_threshold")
    @classmethod
    def validate_cache_distance(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 2:
            raise ValueError("cache distance must be in Redis cosine-distance range [0, 2]")
        return value

    @property
    def active_embedding_provider(self) -> EmbeddingProvider:
        if self.embedding_provider is not None:
            return self.embedding_provider
        return "jina" if self.profile == "cloud" else "fastembed"

    @property
    def active_reranker_provider(self) -> RerankerProvider:
        if self.reranker_provider is not None:
            return self.reranker_provider
        return "jina" if self.profile == "cloud" else "fastembed"

    @property
    def active_stt_provider(self) -> TranscriberProvider:
        if self.stt_provider is not None:
            return self.stt_provider
        return "sarvam" if self.sarvam_api_key else "none"

    @property
    def effective_request_deadline_seconds(self) -> float:
        """Cloud hops (Jina, Groq, Qdrant) need more wall-clock than the local rig."""
        if self.profile == "cloud":
            return max(self.request_deadline_seconds, 60.0)
        return self.request_deadline_seconds

    @property
    def effective_llm_timeout_seconds(self) -> float:
        if self.profile == "cloud":
            return max(self.llm_timeout_seconds, 45.0)
        return self.llm_timeout_seconds

    @property
    def uses_hosted_embedding(self) -> bool:
        return self.active_embedding_provider != "fastembed"

    @property
    def uses_hosted_reranker(self) -> bool:
        return self.active_reranker_provider != "fastembed"

    @property
    def active_dense_model_id(self) -> str:
        if self.active_embedding_provider == "jina":
            return self.jina_embedding_model
        return self.dense_model_id

    @property
    def active_dense_dimension(self) -> int:
        if self.active_embedding_provider == "jina":
            return self.jina_embedding_dimension
        return self.dense_dimension

    @property
    def active_dense_query_prefix(self) -> str:
        # Hosted models take a task parameter instead of a textual prefix.
        return "" if self.uses_hosted_embedding else self.dense_query_prefix

    @property
    def active_dense_revision(self) -> str:
        return HOSTED_REVISION if self.uses_hosted_embedding else self.dense_model_revision

    @property
    def active_dense_artifact(self) -> str:
        """Fingerprint component standing in for a local checksum on hosted models."""
        if self.uses_hosted_embedding:
            return f"{self.active_embedding_provider}:{self.active_dense_model_id}"
        return self.dense_model_sha256

    @property
    def active_reranker_model_id(self) -> str:
        if self.active_reranker_provider == "jina":
            return self.jina_reranker_model
        return self.reranker_model_id

    @property
    def active_reranker_revision(self) -> str:
        return HOSTED_REVISION if self.uses_hosted_reranker else self.reranker_revision

    @property
    def active_reranker_artifact(self) -> str:
        if self.uses_hosted_reranker:
            return f"{self.active_reranker_provider}:{self.active_reranker_model_id}"
        return self.reranker_sha256

    @property
    def chunk_strategy_list(self) -> list[str]:
        return [name.strip() for name in self.chunk_strategies.split(",") if name.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def guardrail_language_set(self) -> set[str]:
        codes = self.guardrail_languages.split(",")
        return {code.strip().casefold() for code in codes if code.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
