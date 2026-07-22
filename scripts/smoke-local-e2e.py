#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
from collections.abc import Sequence

import httpx
from pydantic import SecretStr

from fastrag.adapters.generation import OpenAICompatibleGenerator
from fastrag.api import create_app
from fastrag.calibration import Calibration
from fastrag.config import Settings
from fastrag.domain import CachedAnswer, Chunk, Citation, RankedChunk
from fastrag.pipeline import PipelineConfig, QueryPipeline


class MemoryEmbedder:
    async def embed_query(self, query: str) -> list[float]:
        return [1.0, 0.0]

    async def embed_documents(self, documents: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in documents]


class MemoryRetriever:
    def __init__(self, chunk: Chunk) -> None:
        self._chunk = chunk

    async def retrieve(
        self,
        query: str,
        vector: list[float],
        limit: int,
        *,
        collection: str | None = None,
    ) -> list[Chunk]:
        return [self._chunk]


class MemoryReranker:
    async def rerank(
        self, query: str, candidates: Sequence[Chunk], limit: int
    ) -> list[RankedChunk]:
        return [RankedChunk(chunk=chunk, score=0.99) for chunk in candidates[:limit]]


class NoopCache:
    async def get_exact(self, namespace: str, query: str) -> CachedAnswer | None:
        return None

    async def get_semantic(self, namespace: str, vector: list[float]) -> CachedAnswer | None:
        return None

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
        return None


async def run(args: argparse.Namespace) -> int:
    chunk = Chunk(
        chunk_id="local-e2e-1",
        document_id="local-e2e-doc",
        text="The FastRAG local end-to-end smoke test refund period is thirty days.",
        title="Local E2E fixture",
        source_uri="memory://local-e2e",
    )
    generator = OpenAICompatibleGenerator(
        base_url=args.llm_base_url,
        api_key=args.llm_api_key,
        model=args.llm_model,
        system_prompt=(
            "Answer only from the supplied sources. Every factual sentence must end with "
            "the exact marker [C:local-e2e-1]. Do not cite anything else."
        ),
        max_tokens=80,
        timeout_seconds=args.timeout,
    )
    pipeline = QueryPipeline(
        embedder=MemoryEmbedder(),
        retriever=MemoryRetriever(chunk),
        reranker=MemoryReranker(),
        generator=generator,
        cache=NoopCache(),
        calibration=Calibration(
            reranker_threshold=0.5,
            reranker_fingerprint="local-reranker",
            embedding_fingerprint="local-embedding",
            false_answer_rate=0.0,
            sample_count=30,
        ),
        config=PipelineConfig(
            embedding_fingerprint="local-embedding",
            reranker_fingerprint="local-reranker",
            prompt_version="local-smoke",
            generator_model=args.llm_model,
            max_answer_tokens=80,
            content_version="local-e2e",
        ),
    )
    settings = Settings(
        environment="local-smoke",
        release="local-smoke",
        query_api_key=SecretStr(args.query_key),
        admin_api_key=SecretStr("unused-admin"),
    )
    app = create_app(settings=settings, pipeline=pipeline)
    app.state.pipeline = pipeline
    app.state.ready = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/query",
            headers={"Authorization": f"Bearer {args.query_key}"},
            json={"query": "What is the local smoke test refund period?"},
        )
    response.raise_for_status()
    payload = response.json()
    print(payload["answer"])
    if payload["outcome"] != "answered":
        print(f"Unexpected outcome: {payload['outcome']}")
        return 1
    if payload["citations"][0]["chunk_id"] != "local-e2e-1":
        print(f"Unexpected citations: {payload['citations']}")
        return 1
    if "thirty days" not in payload["answer"].lower():
        print("Unexpected answer content.")
        return 1
    if os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        from langfuse import get_client

        get_client().flush()
        print(f"Langfuse trace flushed: {payload['trace_id']}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a local FastAPI + pipeline + Ollama + Langfuse smoke test"
    )
    parser.add_argument(
        "--llm-base-url", default=os.getenv("FASTRAG_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    )
    parser.add_argument("--llm-api-key", default=os.getenv("FASTRAG_LLM_API_KEY", "ollama"))
    parser.add_argument("--llm-model", default=os.getenv("FASTRAG_LLM_MODEL", "llama3.2:latest"))
    parser.add_argument("--query-key", default="local-query-key")
    parser.add_argument("--timeout", type=float, default=30.0)
    raise SystemExit(asyncio.run(run(parser.parse_args())))


if __name__ == "__main__":
    main()
