from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .domain import ActiveIndex


@dataclass(frozen=True, slots=True)
class IndexManifest:
    index_version: str
    collection_name: str
    content_version: str
    embedding_fingerprint: str
    chunk_size: int
    chunk_overlap: int
    state: str = "building"


class PostgresIndexRegistry:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        with psycopg.connect(self._database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS index_manifests (
                    index_version TEXT PRIMARY KEY,
                    collection_name TEXT NOT NULL,
                    content_version TEXT NOT NULL,
                    embedding_fingerprint TEXT NOT NULL,
                    state TEXT NOT NULL CHECK (
                      state IN ('building','validated','active','retired','failed')
                    ),
                    manifest JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    activated_at TIMESTAMPTZ
                )
                """
            )
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_index
                ON index_manifests ((state)) WHERE state = 'active'
                """
            )

    async def register(self, manifest: IndexManifest) -> None:
        await asyncio.to_thread(self._register_sync, manifest)

    def _register_sync(self, manifest: IndexManifest) -> None:
        with psycopg.connect(self._database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO index_manifests
                  (index_version, collection_name, content_version,
                   embedding_fingerprint, state, manifest)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (index_version) DO UPDATE SET
                  collection_name=excluded.collection_name,
                  content_version=excluded.content_version,
                  embedding_fingerprint=excluded.embedding_fingerprint,
                  state=excluded.state,
                  manifest=excluded.manifest
                """,
                (
                    manifest.index_version,
                    manifest.collection_name,
                    manifest.content_version,
                    manifest.embedding_fingerprint,
                    manifest.state,
                    json.dumps(asdict(manifest)),
                ),
            )

    async def mark_validated(self, index_version: str) -> None:
        await self._set_state(index_version, "validated")

    async def mark_failed(self, index_version: str) -> None:
        await self._set_state(index_version, "failed")

    async def activate(self, index_version: str) -> None:
        await asyncio.to_thread(self._activate_sync, index_version)

    def _activate_sync(self, index_version: str) -> None:
        with psycopg.connect(self._database_url) as connection, connection.cursor() as cursor:
            cursor.execute("UPDATE index_manifests SET state='retired' WHERE state='active'")
            cursor.execute(
                """
                UPDATE index_manifests SET state='active', activated_at=%s
                WHERE index_version=%s AND state='validated'
                """,
                (datetime.now(UTC), index_version),
            )
            if cursor.rowcount != 1:
                raise RuntimeError("index must be validated before activation")

    async def _set_state(self, index_version: str, state: str) -> None:
        await asyncio.to_thread(self._set_state_sync, index_version, state)

    def _set_state_sync(self, index_version: str, state: str) -> None:
        with psycopg.connect(self._database_url) as connection, connection.cursor() as cursor:
            cursor.execute(
                "UPDATE index_manifests SET state=%s WHERE index_version=%s",
                (state, index_version),
            )
            if cursor.rowcount != 1:
                raise KeyError(index_version)

    async def active(self) -> dict[str, Any] | None:
        return await asyncio.to_thread(self._active_sync)

    def _active_sync(self) -> dict[str, Any] | None:
        with psycopg.connect(self._database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                "SELECT * FROM index_manifests WHERE state='active'"
            ).fetchone()
            return dict(row) if row else None

    async def active_content_version(self) -> str:
        active = await self.active()
        if active is None:
            raise RuntimeError("no active index")
        return str(active["content_version"])

    async def active_collection_name(self) -> str:
        active = await self.active()
        if active is None:
            raise RuntimeError("no active index")
        return str(active["collection_name"])

    async def active_snapshot(self) -> ActiveIndex:
        active = await self.active()
        if active is None:
            raise RuntimeError("no active index")
        return ActiveIndex(
            content_version=str(active["content_version"]),
            collection_name=str(active["collection_name"]),
        )

    async def assert_embedding_fingerprint(self, fingerprint: str) -> None:
        active = await self.active()
        if active is not None and active["embedding_fingerprint"] != fingerprint:
            raise RuntimeError("active index embedding fingerprint mismatch")
