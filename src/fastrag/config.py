from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    retrieval_leg_k: int = 20
    retrieval_candidate_k: int = 20
    context_top_k: int = 5
    max_context_tokens: int = 2400
    max_answer_tokens: int = 200

    calibration_path: Path = Path("config/calibration.json")
    prompt_path: Path = Path("config/system_prompt.txt")
    prompt_version: str = "v1"

    llm_base_url: str = "http://llm-gateway:8000/v1"
    llm_api_key: SecretStr = SecretStr("not-configured")
    llm_model: str = "configured-at-deploy"
    llm_timeout_seconds: float = 20.0

    cache_ttl_seconds: int = 604_800
    cache_distance_threshold: float | None = None
    content_version: str = "empty"

    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = "http://langfuse-web:3000"
    trace_raw_content: bool = False

    data_dir: Path = Path("/data")
    database_url: str = "postgresql://fastrag:fastrag@postgres:5432/fastrag"

    @field_validator("retrieval_candidate_k")
    @classmethod
    def candidate_k_must_cover_context(cls, value: int, info: object) -> int:
        if value < 1:
            raise ValueError("retrieval_candidate_k must be positive")
        return value

    @field_validator("cache_distance_threshold")
    @classmethod
    def validate_cache_distance(cls, value: float | None) -> float | None:
        if value is not None and not 0 <= value <= 2:
            raise ValueError("cache distance must be in Redis cosine-distance range [0, 2]")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
