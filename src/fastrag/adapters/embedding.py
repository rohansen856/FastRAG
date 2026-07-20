from __future__ import annotations

import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any


class FastEmbedder:
    def __init__(
        self,
        model_id: str,
        *,
        query_prefix: str = "",
        normalize: bool = True,
        model_path: Path | None = None,
    ) -> None:
        from fastembed import TextEmbedding

        self._model: Any = TextEmbedding(
            model_name=model_id,
            specific_model_path=str(model_path) if model_path else None,
            local_files_only=model_path is not None,
        )
        self._query_prefix = query_prefix
        self._normalize = normalize

    async def embed_query(self, query: str) -> list[float]:
        vectors = await asyncio.to_thread(
            lambda: list(self._model.query_embed([self._query_prefix + query]))
        )
        return self._as_list(vectors[0])

    async def embed_documents(self, documents: Sequence[str]) -> list[list[float]]:
        vectors = await asyncio.to_thread(lambda: list(self._model.passage_embed(list(documents))))
        return [self._as_list(vector) for vector in vectors]

    def _as_list(self, vector: Any) -> list[float]:
        values = [float(value) for value in vector]
        if not self._normalize:
            return values
        magnitude = sum(value * value for value in values) ** 0.5
        return values if magnitude == 0 else [value / magnitude for value in values]
