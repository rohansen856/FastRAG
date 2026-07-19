import pytest
from conftest import MemoryCache, make_pipeline

from fastrag.domain import CachedAnswer, CacheStatus, Outcome
from fastrag.pipeline import NO_ANSWER_TEXT, PipelineUnavailable


@pytest.mark.asyncio
async def test_answer_is_grounded_and_cached(chunk):
    pipeline, cache = make_pipeline(chunk)
    response = await pipeline.run("What is the refund period?")
    assert response.outcome is Outcome.ANSWERED
    assert response.answer == "The refund period is thirty days [1]."
    assert response.citations[0].chunk_id == "chunk-1"
    assert cache.writes[0]["semantic"] is True


@pytest.mark.asyncio
async def test_low_reranker_score_abstains_and_only_exact_caches(chunk):
    pipeline, cache = make_pipeline(chunk, score=0.1)
    response = await pipeline.run("Unknown?")
    assert response.outcome is Outcome.NO_ANSWER
    assert response.answer == NO_ANSWER_TEXT
    assert cache.writes[0]["semantic"] is False


@pytest.mark.asyncio
async def test_exact_cache_skips_pipeline(chunk):
    cache = MemoryCache()
    cache.exact = CachedAnswer(
        answer="Cached answer",
        citations=(),
        outcome=Outcome.ANSWERED,
        cache_status=CacheStatus.EXACT,
    )
    pipeline, _ = make_pipeline(chunk, cache=cache)
    response = await pipeline.run("repeat")
    assert response.answer == "Cached answer"
    assert response.cache_status is CacheStatus.EXACT


@pytest.mark.asyncio
async def test_invalid_model_citation_fails_closed(chunk):
    pipeline, _ = make_pipeline(chunk, output="Claim. [C:unknown]")
    with pytest.raises(PipelineUnavailable) as error:
        await pipeline.run("Question")
    assert error.value.stage == "citation_validation"


@pytest.mark.asyncio
async def test_context_budget_is_enforced(chunk):
    pipeline, _ = make_pipeline(chunk)
    pipeline._config.max_context_tokens = 1
    response = await pipeline.run("Question")
    assert response.outcome is Outcome.NO_ANSWER
