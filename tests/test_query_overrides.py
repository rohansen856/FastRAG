from dataclasses import replace

import httpx
import pytest
from conftest import MemoryCache, make_pipeline
from pydantic import SecretStr

from fastrag.api import create_app
from fastrag.config import Settings
from fastrag.domain import CachedAnswer, CacheStatus, Outcome, QueryOverrides


@pytest.mark.asyncio
async def test_skip_cache_bypasses_exact_hit(chunk):
    cache = MemoryCache()
    cache.exact = CachedAnswer(
        answer="Cached answer",
        citations=(),
        outcome=Outcome.ANSWERED,
        cache_status=CacheStatus.EXACT,
    )
    pipeline, _ = make_pipeline(chunk, cache=cache)
    response = await pipeline.run(
        "What is the refund period?",
        overrides=QueryOverrides(skip_cache=True),
    )
    assert response.outcome is Outcome.ANSWERED
    assert response.answer == "The refund period is thirty days [1]."
    assert response.cache_status is CacheStatus.MISS
    trace = response.trace
    assert trace is not None
    exact = next(stage for stage in trace.stages if stage.id == "exact_cache")
    semantic = next(stage for stage in trace.stages if stage.id == "semantic_cache")
    assert exact.status == "skipped"
    assert semantic.status == "skipped"
    assert trace.overrides_applied == {"skip_cache": True}


@pytest.mark.asyncio
async def test_crag_disabled_via_override(chunk):
    pipeline, _ = make_pipeline(chunk, score=0.1)
    response = await pipeline.run("Unknown?", overrides=QueryOverrides(crag_enabled=False))
    assert response.outcome is Outcome.NO_ANSWER
    crag = next(stage for stage in response.trace.stages if stage.id == "crag")
    assert crag.status == "skipped"
    assert crag.detail == "CRAG disabled"


@pytest.mark.asyncio
async def test_candidate_k_limits_retrieval(chunk):
    other = replace(
        chunk,
        chunk_id="chunk-2",
        document_id="doc-2",
        text="Another policy paragraph with more detail.",
        title="Other",
    )
    from conftest import FakeRetriever

    pipeline, _ = make_pipeline(chunk)
    pipeline._retriever = FakeRetriever([chunk, other])  # noqa: SLF001
    response = await pipeline.run(
        "Question",
        overrides=QueryOverrides(candidate_k=1, context_top_k=1),
    )
    trace = response.trace
    assert trace is not None
    assert len(trace.retrieved) == 1
    assert len(trace.contexts) == 1


@pytest.mark.asyncio
async def test_reranker_threshold_override_abstains(chunk):
    pipeline, _ = make_pipeline(chunk, score=0.6)
    response = await pipeline.run("Question", overrides=QueryOverrides(reranker_threshold=0.95))
    assert response.outcome is Outcome.NO_ANSWER


@pytest.mark.asyncio
async def test_reranker_threshold_override_answers(chunk):
    pipeline, _ = make_pipeline(chunk, score=0.6)
    response = await pipeline.run("Question", overrides=QueryOverrides(reranker_threshold=0.1))
    assert response.outcome is Outcome.ANSWERED


@pytest.mark.asyncio
async def test_llm_model_override_in_trace(chunk):
    pipeline, _ = make_pipeline(chunk)
    response = await pipeline.run(
        "Question",
        overrides=QueryOverrides(llm={"model": "custom-model"}),
    )
    assert response.trace is not None
    assert response.trace.generator_model == "custom-model"
    assert response.trace.overrides_applied == {"llm": {"model": "custom-model"}}


@pytest.mark.asyncio
async def test_api_rejects_overrides_when_disabled(chunk):
    pipeline, _ = make_pipeline(chunk)
    settings = Settings(
        query_api_key=SecretStr("query-secret"),
        admin_api_key=SecretStr("admin-secret"),
        allow_query_overrides=False,
    )
    app = create_app(settings=settings, pipeline=pipeline)
    app.state.pipeline = pipeline
    app.state.ready = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/query",
            headers={"Authorization": "Bearer query-secret"},
            json={"query": "refund", "overrides": {"skip_cache": True}},
        )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_api_accepts_negative_offtopic_threshold(chunk):
    pipeline, _ = make_pipeline(chunk)
    settings = Settings(
        query_api_key=SecretStr("query-secret"),
        admin_api_key=SecretStr("admin-secret"),
        allow_query_overrides=True,
    )
    app = create_app(settings=settings, pipeline=pipeline)
    app.state.pipeline = pipeline
    app.state.ready = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/query",
            headers={"Authorization": "Bearer query-secret"},
            json={"query": "refund", "overrides": {"offtopic_threshold": -0.121}},
        )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_api_accepts_overrides(chunk):
    pipeline, _ = make_pipeline(chunk)
    settings = Settings(
        query_api_key=SecretStr("query-secret"),
        admin_api_key=SecretStr("admin-secret"),
        allow_query_overrides=True,
    )
    app = create_app(settings=settings, pipeline=pipeline)
    app.state.pipeline = pipeline
    app.state.ready = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/v1/query",
            headers={"Authorization": "Bearer query-secret"},
            json={"query": "refund", "overrides": {"skip_cache": True}},
        )
    assert response.status_code == 200
    assert response.json()["trace"]["overrides_applied"] == {"skip_cache": True}
