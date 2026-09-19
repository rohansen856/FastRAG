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
        document_prefix: str = "",
        normalize: bool = True,
        model_path: Path | None = None,
        providers: list[str] | None = None,
        batch_size: int | None = None,
    ) -> None:
        from fastembed import TextEmbedding

        # Only pass `providers` when set, so the default stays FastEmbed's own choice.
        placement: dict[str, Any] = {"providers": providers} if providers else {}
        self._model: Any = TextEmbedding(
            model_name=model_id,
            specific_model_path=str(model_path) if model_path else None,
            local_files_only=model_path is not None,
            **placement,
        )
        self._query_prefix = query_prefix
        # Asymmetric models such as E5 are trained with a marker on both sides
        # ("query: " / "passage: "); omitting the passage one measurably hurts recall.
        self._document_prefix = document_prefix
        self._normalize = normalize
        # Unset keeps FastEmbed's default. A GPU holding E5's 2.2 GB of weights has too
        # little left for the attention buffers of 24 long passages at once.
        self._batching: dict[str, Any] = {"batch_size": batch_size} if batch_size else {}

    async def embed_query(self, query: str, *, deadline: object = None) -> list[float]:
        vectors = await asyncio.to_thread(
            lambda: list(self._model.query_embed([self._query_prefix + query]))
        )
        return self._as_list(vectors[0])

    async def embed_documents(
        self, documents: Sequence[str], *, deadline: object = None
    ) -> list[list[float]]:
        if not documents:
            return []
        vectors = await asyncio.to_thread(
            lambda: list(
                self._model.passage_embed(
                    [self._document_prefix + text for text in documents], **self._batching
                )
            )
        )
        return [self._as_list(vector) for vector in vectors]

    def _as_list(self, vector: Any) -> list[float]:
        values = [float(value) for value in vector]
        if not self._normalize:
            return values
        magnitude = sum(value * value for value in values) ** 0.5
        return values if magnitude == 0 else [value / magnitude for value in values]
