from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from conftest import FakeEmbedder, FakeGenerator, FakeReranker, FakeRetriever, MemoryCache

from fastrag.calibration import Calibration
from fastrag.crag import CorrectiveRetrieval
from fastrag.documents import parse_file
from fastrag.guardrails import Guardrails
from fastrag.pipeline import PipelineConfig, QueryPipeline


@pytest.mark.asyncio
async def test_parse_text_and_json(tmp_path: Path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("Hello from a plain text upload.", encoding="utf-8")
    doc = parse_file(text_path, document_id="user-test", title="Notes")
    assert doc.document_id == "user-test"
    assert "plain text" in doc.text

    json_path = tmp_path / "data.json"
    json_path.write_text(json.dumps({"topic": "refunds", "days": 30}), encoding="utf-8")
    parsed = parse_file(json_path, document_id="user-json", title="Data")
    assert "refunds" in parsed.text
    assert "30" in parsed.text


@pytest.mark.asyncio
async def test_retriever_filters_by_document_id(chunk) -> None:
    other = replace(chunk, chunk_id="chunk-2", document_id="doc-2")
    retriever = FakeRetriever([chunk, other])
    results = await retriever.retrieve(
        "refund",
        [1.0, 0.0],
        5,
        document_ids=["doc-2"],
    )
    assert len(results) == 1
    assert results[0].document_id == "doc-2"
    assert retriever.calls[-1]["document_ids"] == ["doc-2"]


@pytest.mark.asyncio
async def test_corpus_retrieval_excludes_session_uploads(chunk) -> None:
    session = replace(
        chunk,
        chunk_id="session-1",
        document_id="user-abc",
        metadata={"session_upload": True},
    )
    retriever = FakeRetriever([chunk, session])
    corpus = await retriever.retrieve("refund", [1.0, 0.0], 5)
    assert len(corpus) == 1
    assert corpus[0].document_id == "doc-1"

    scoped = await retriever.retrieve(
        "refund",
        [1.0, 0.0],
        5,
        document_ids=["user-abc"],
    )
    assert len(scoped) == 1
    assert scoped[0].document_id == "user-abc"


@pytest.mark.asyncio
async def test_scoped_query_skips_vector_guardrail(chunk) -> None:
    """User uploads should not be rejected by the MSMARCO corpus centroid."""
    calibration = Calibration(
        reranker_threshold=0.5,
        reranker_fingerprint="reranker",
        embedding_fingerprint="embedding",
        false_answer_rate=0.0,
        sample_count=30,
        offtopic_threshold=0.99,
    )
    guardrails = Guardrails(
        enabled=True,
        corpus_centroid=[1.0, 0.0],
        offtopic_threshold=0.99,
    )
    pipeline = QueryPipeline(
        embedder=FakeEmbedder([0.0, 1.0]),
        retriever=FakeRetriever([chunk]),
        reranker=FakeReranker(0.9),
        generator=FakeGenerator("Scoped answer [C:chunk-1]."),
        cache=MemoryCache(),
        calibration=calibration,
        guardrails=guardrails,
        config=PipelineConfig(
            embedding_fingerprint="embedding",
            reranker_fingerprint="reranker",
            prompt_version="v1",
            generator_model="test-model",
            max_answer_tokens=200,
            content_version="test-index",
        ),
    )

    blocked = await pipeline.run("What is the refund period?", document_id=None)
    assert blocked.outcome == "refused"

    answered = await pipeline.run("What is the refund period?", document_id="doc-1")
    assert answered.outcome == "answered"


@pytest.mark.asyncio
async def test_scoped_query_answers_despite_low_rerank(chunk) -> None:
    """Attached documents should answer even when rerank scores miss MSMARCO calibration."""
    calibration = Calibration(
        reranker_threshold=0.95,
        crag_confident_threshold=0.99,
        reranker_fingerprint="reranker",
        embedding_fingerprint="embedding",
        false_answer_rate=0.0,
        sample_count=30,
    )
    crag = CorrectiveRetrieval(
        calibration=calibration,
        reranker=FakeReranker(0.2),
        retriever=FakeRetriever([chunk]),
        embedder=FakeEmbedder(),
        generator=FakeGenerator("Rohan is a software engineer [C:chunk-1]."),
        enabled=True,
    )
    pipeline = QueryPipeline(
        embedder=FakeEmbedder(),
        retriever=FakeRetriever([chunk]),
        reranker=FakeReranker(0.2),
        generator=FakeGenerator("Rohan is a software engineer [C:chunk-1]."),
        cache=MemoryCache(),
        calibration=calibration,
        crag=crag,
        config=PipelineConfig(
            embedding_fingerprint="embedding",
            reranker_fingerprint="reranker",
            prompt_version="v1",
            generator_model="test-model",
            max_answer_tokens=200,
            content_version="test-index",
        ),
    )

    corpus = await pipeline.run("Who is Rohan?", document_id=None)
    assert corpus.outcome == "no_answer"

    scoped = await pipeline.run("Who is Rohan?", document_id="doc-1")
    assert scoped.outcome == "answered"
