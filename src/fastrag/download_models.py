from __future__ import annotations

from huggingface_hub import snapshot_download

from .config import Settings
from .model_artifacts import verify_configured_models

# Models with external weights (E5) keep them in `*.onnx_data` beside the graph.
ARTIFACT_PATTERNS = ["*.json", "*.txt", "*.onnx", "*.onnx_data"]


def main() -> None:
    settings = Settings()
    if settings.dense_model_path is None or settings.reranker_model_path is None:
        raise RuntimeError("FASTRAG_DENSE_MODEL_PATH and FASTRAG_RERANKER_MODEL_PATH are required")
    snapshot_download(
        repo_id=settings.dense_model_repository,
        revision=settings.dense_model_revision,
        local_dir=settings.dense_model_path,
        allow_patterns=ARTIFACT_PATTERNS,
    )
    snapshot_download(
        repo_id=settings.reranker_model_repository,
        revision=settings.reranker_revision,
        local_dir=settings.reranker_model_path,
        allow_patterns=ARTIFACT_PATTERNS,
    )
    verify_configured_models(settings)
    print("downloaded and checksum-verified dense and reranker artifacts")


if __name__ == "__main__":
    main()
