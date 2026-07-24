from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


class CalibrationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Calibration:
    reranker_threshold: float
    reranker_fingerprint: str
    embedding_fingerprint: str
    false_answer_rate: float
    sample_count: int
    cache_distance_threshold: float | None = None
    # Upper CRAG band. Scores at or above this are trusted without correction;
    # scores between `reranker_threshold` and this are ambiguous and get refined.
    crag_confident_threshold: float | None = None
    offtopic_threshold: float | None = None

    @property
    def crag_upper(self) -> float:
        """Confidence needed to skip correction entirely."""
        if self.crag_confident_threshold is None:
            return self.reranker_threshold
        return max(self.crag_confident_threshold, self.reranker_threshold)

    @classmethod
    def load(cls, path: Path) -> Calibration:
        try:
            payload = json.loads(path.read_text())
            calibration = cls(
                reranker_threshold=float(payload["reranker_threshold"]),
                reranker_fingerprint=str(payload["reranker_fingerprint"]),
                embedding_fingerprint=str(payload["embedding_fingerprint"]),
                false_answer_rate=float(payload["false_answer_rate"]),
                sample_count=int(payload["sample_count"]),
                cache_distance_threshold=(
                    float(payload["cache_distance_threshold"])
                    if payload.get("cache_distance_threshold") is not None
                    else None
                ),
                crag_confident_threshold=(
                    float(payload["crag_confident_threshold"])
                    if payload.get("crag_confident_threshold") is not None
                    else None
                ),
                offtopic_threshold=(
                    float(payload["offtopic_threshold"])
                    if payload.get("offtopic_threshold") is not None
                    else None
                ),
            )
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise CalibrationError(f"invalid calibration artifact {path}: {exc}") from exc
        if calibration.false_answer_rate > 0.05:
            raise CalibrationError("calibration false_answer_rate exceeds 0.05")
        if calibration.sample_count < 30:
            raise CalibrationError("calibration requires at least 30 labeled samples")
        if (
            calibration.cache_distance_threshold is not None
            and not 0 <= calibration.cache_distance_threshold <= 2
        ):
            raise CalibrationError("cache distance threshold must be in [0, 2]")
        return calibration

    def validate(self, *, reranker_fingerprint: str, embedding_fingerprint: str) -> None:
        if self.reranker_fingerprint != reranker_fingerprint:
            raise CalibrationError("reranker fingerprint does not match calibration")
        if self.embedding_fingerprint != embedding_fingerprint:
            raise CalibrationError("embedding fingerprint does not match calibration")
