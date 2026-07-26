from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings


class ModelArtifactError(RuntimeError):
    pass


def verify_model_artifact(root: Path, relative_file: str, expected_sha256: str) -> None:
    path = root / relative_file
    if not path.is_file():
        raise ModelArtifactError(f"model artifact is missing: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ModelArtifactError(f"model artifact checksum mismatch: {path}")


def verify_configured_models(settings: Settings) -> None:
    """Checksum every model that runs in-process.

    Hosted providers have no local artifact to hash; their fingerprint is the
    provider/model pair instead, and the provider is responsible for the weights.
    """
    if settings.environment != "production":
        return
    if not settings.uses_hosted_embedding:
        if settings.dense_model_path is None:
            raise ModelArtifactError("production requires a local, checksum-verified dense model")
        verify_model_artifact(
            settings.dense_model_path,
            settings.dense_model_file,
            settings.dense_model_sha256,
        )
    if not settings.uses_hosted_reranker:
        if settings.reranker_model_path is None:
            raise ModelArtifactError("production requires a local, checksum-verified reranker")
        verify_model_artifact(
            settings.reranker_model_path,
            settings.reranker_model_file,
            settings.reranker_sha256,
        )
