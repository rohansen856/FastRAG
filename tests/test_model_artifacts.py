import hashlib

import pytest

from fastrag.model_artifacts import ModelArtifactError, verify_model_artifact


def test_model_artifact_checksum(tmp_path):
    artifact = tmp_path / "model.onnx"
    artifact.write_bytes(b"verified model")
    checksum = hashlib.sha256(artifact.read_bytes()).hexdigest()
    verify_model_artifact(tmp_path, "model.onnx", checksum)
    with pytest.raises(ModelArtifactError, match="checksum mismatch"):
        verify_model_artifact(tmp_path, "model.onnx", "0" * 64)
