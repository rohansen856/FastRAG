from __future__ import annotations

from huggingface_hub import snapshot_download

from .config import Settings
from .model_artifacts import verify_configured_models

DENSE_REPOSITORY = "qdrant/bge-base-en-v1.5-onnx-q"
RERANKER_REPOSITORY = "Xenova/ms-marco-MiniLM-L-6-v2"


def main() -> None:
    settings = Settings()
    if settings.dense_model_path is None or settings.reranker_model_path is None:
        raise RuntimeError("FASTRAG_DENSE_MODEL_PATH and FASTRAG_RERANKER_MODEL_PATH are required")
    snapshot_download(
        repo_id=DENSE_REPOSITORY,
        revision=settings.dense_model_revision,
        local_dir=settings.dense_model_path,
        allow_patterns=["*.json", "*.txt", "*.onnx"],
    )
    snapshot_download(
        repo_id=RERANKER_REPOSITORY,
        revision=settings.reranker_revision,
        local_dir=settings.reranker_model_path,
        allow_patterns=["*.json", "*.txt", "*.onnx"],
    )
    verify_configured_models(settings)
    print("downloaded and checksum-verified dense and reranker artifacts")


if __name__ == "__main__":
    main()
