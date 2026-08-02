from __future__ import annotations

import hashlib
import json
import re
import uuid
from array import array
from collections.abc import Sequence
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ResponseError, TimeoutError as RedisTimeoutError

from ..domain import CachedAnswer, CacheStatus, Citation, Outcome


def normalize_query(query: str) -> str:
    return " ".join(query.casefold().split())


def _module_missing(exc: ResponseError) -> bool:
    return "unknown command" in str(exc).casefold()


def _index_missing(exc: ResponseError) -> bool:
    message = str(exc).casefold()
    return "unknown index name" in message or "no such index" in message


class RedisAnswerCache:
    def __init__(
        self,
        redis_url: str,
        *,
        embedding_fingerprint: str,
        dimension: int,
        ttl_seconds: int,
        distance_threshold: float | None,
        semantic_enabled: bool = True,
    ) -> None:
        self._redis = Redis.from_url(
            redis_url,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        fingerprint_prefix = embedding_fingerprint[:16]
        self._index_name = f"fastrag-semantic-{fingerprint_prefix}"
        self._semantic_prefix = f"fastrag:semantic:{fingerprint_prefix}:"
        self._dimension = dimension
        self._ttl = ttl_seconds
        self._threshold = distance_threshold
        self._semantic_enabled = semantic_enabled
        self._available = True

    @property
    def semantic_enabled(self) -> bool:
        return self._semantic_enabled

    async def initialize(self) -> None:
        """Create the vector index, degrading to exact-only if unsupported.

        Managed Redis without the search module (Upstash, for example) rejects
        FT.* outright. The exact cache still works there, so we disable the
        semantic tier rather than failing startup.
        """
        try:
            await self._redis.ping()
        except (OSError, TimeoutError, ConnectionError, RedisTimeoutError):
            # Unreachable Redis must not block process startup; lookups fail open.
            self._available = False
            self._semantic_enabled = False
            return
        if not self._semantic_enabled:
            return
        try:
            await self._redis.execute_command("FT.INFO", self._index_name)
            return
        except ResponseError as exc:
            if _module_missing(exc):
                self._semantic_enabled = False
                return
            if not _index_missing(exc):
                raise
        try:
            await self._redis.execute_command(
                "FT.CREATE",
                self._index_name,
                "ON",
                "HASH",
                "PREFIX",
                1,
                self._semantic_prefix,
                "SCHEMA",
                "namespace",
                "TAG",
                "payload",
                "TEXT",
                "embedding",
                "VECTOR",
                "HNSW",
                10,
                "TYPE",
                "FLOAT32",
                "DIM",
                self._dimension,
                "DISTANCE_METRIC",
                "COSINE",
                "M",
                16,
                "EF_CONSTRUCTION",
                200,
            )
        except ResponseError as exc:
            if not _module_missing(exc):
                raise
            self._semantic_enabled = False

    async def get_exact(self, namespace: str, query: str) -> CachedAnswer | None:
        if not self._available:
            return None
        value = await self._redis.get(self._exact_key(namespace, query))
        return self._decode(value, CacheStatus.EXACT) if value else None

    async def get_semantic(self, namespace: str, vector: list[float]) -> CachedAnswer | None:
        if self._threshold is None or not self._semantic_enabled or not self._available:
            return None
        safe_namespace = re.sub(r"[^A-Za-z0-9_-]", "_", namespace)
        response: list[Any] = await self._redis.execute_command(
            "FT.SEARCH",
            self._index_name,
            f"(@namespace:{{{safe_namespace}}})=>[KNN 1 @embedding $vector AS distance]",
            "PARAMS",
            2,
            "vector",
            self._vector_bytes(vector),
            "SORTBY",
            "distance",
            "RETURN",
            2,
            "payload",
            "distance",
            "DIALECT",
            2,
        )
        if not response or int(response[0]) == 0:
            return None
        fields = self._field_map(response[2])
        distance = float(fields[b"distance"])
        if distance > self._threshold:
            return None
        return self._decode(fields[b"payload"], CacheStatus.SEMANTIC)

    async def put(
        self,
        namespace: str,
        query: str,
        vector: list[float] | None,
        answer: str,
        citations: Sequence[Citation],
        *,
        semantic: bool,
    ) -> None:
        if not self._available:
            return
        payload = json.dumps(
            {
                "answer": answer,
                "citations": [citation.model_dump(mode="json") for citation in citations],
                "outcome": Outcome.ANSWERED if semantic else Outcome.NO_ANSWER,
            },
            separators=(",", ":"),
        )
        await self._redis.set(self._exact_key(namespace, query), payload, ex=self._ttl)
        writes_semantic = self._semantic_enabled and self._threshold is not None
        if semantic and vector is not None and writes_semantic:
            key = f"{self._semantic_prefix}{uuid.uuid4().hex}"
            await self._redis.hset(
                key,
                mapping={
                    "namespace": namespace,
                    "payload": payload,
                    "embedding": self._vector_bytes(vector),
                },
            )
            await self._redis.expire(key, self._ttl)

    @staticmethod
    def _field_map(fields: list[Any]) -> dict[bytes, bytes]:
        return {fields[index]: fields[index + 1] for index in range(0, len(fields), 2)}

    @staticmethod
    def _vector_bytes(vector: list[float]) -> bytes:
        return array("f", vector).tobytes()

    @staticmethod
    def _decode(payload: bytes, status: CacheStatus) -> CachedAnswer:
        decoded = json.loads(payload)
        return CachedAnswer(
            answer=str(decoded["answer"]),
            citations=tuple(Citation.model_validate(item) for item in decoded["citations"]),
            outcome=Outcome(decoded["outcome"]),
            cache_status=status,
        )

    @staticmethod
    def _exact_key(namespace: str, query: str) -> str:
        digest = hashlib.sha256(normalize_query(query).encode()).hexdigest()
        return f"fastrag:exact:{namespace}:{digest}"
