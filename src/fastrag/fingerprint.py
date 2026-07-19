from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class EmbeddingFingerprint:
    model_id: str
    revision: str
    artifact_sha256: str
    dimension: int
    pooling: str = "mean"
    normalize: bool = True
    query_prefix: str = ""
    document_prefix: str = ""
    tokenizer_revision: str = "same-as-model"

    @property
    def digest(self) -> str:
        raw = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()


def cache_namespace(
    *,
    content_version: str,
    embedding_fingerprint: str,
    prompt_version: str,
    generator_model: str,
    max_answer_tokens: int,
    locale: str = "en",
) -> str:
    components = {
        "content": content_version,
        "embedding": embedding_fingerprint,
        "prompt": prompt_version,
        "generator": generator_model,
        "max_tokens": max_answer_tokens,
        "locale": locale,
    }
    raw = json.dumps(components, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:24]
