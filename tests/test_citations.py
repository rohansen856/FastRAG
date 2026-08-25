import pytest

from dataclasses import replace
from fastrag.citations import CitationValidationError, SentenceCitationBuffer


def test_validates_and_numbers_citations(chunk):
    buffer = SentenceCitationBuffer([chunk])
    rendered = buffer.feed("Refunds last thirty days [C:chunk-1]. ")
    rendered += buffer.finish()
    assert rendered == ["Refunds last thirty days [1]."]
    assert buffer.citations()[0].chunk_id == "chunk-1"


def test_accepts_marker_after_the_period(chunk):
    buffer = SentenceCitationBuffer([chunk])
    # Streaming often emits the period before the marker.
    assert buffer.feed("Refunds last thirty days. ") == []
    rendered = buffer.feed("[C:chunk-1] More text. [C:chunk-1] ")
    rendered += buffer.finish()
    assert rendered[0] == "Refunds last thirty days. [1]"


def test_rejects_unknown_citation(chunk, other_chunk):
    buffer = SentenceCitationBuffer([chunk, other_chunk])
    with pytest.raises(CitationValidationError, match="unknown citation"):
        buffer.feed("Unsupported claim [C:made-up]. ")
        buffer.finish()


def test_uncited_single_context_gets_default_marker(chunk):
    buffer = SentenceCitationBuffer([chunk])
    buffer.feed("Uncited claim with no marker")
    rendered = buffer.finish()
    assert rendered[0].startswith("Uncited claim with no marker")
    assert rendered[0].endswith("[1].") or rendered[0].endswith("[1]")
    assert buffer.citations()[0].chunk_id == "chunk-1"


def test_numbered_citation_normalized_for_single_context(chunk):
    buffer = SentenceCitationBuffer([chunk])
    buffer.feed("Rohan worked at Acme [1].")
    rendered = buffer.finish()
    assert rendered == ["Rohan worked at Acme [1]."]


def test_rejects_uncited_sentence_with_multiple_contexts_without_auto_cite(chunk):
    other = replace(chunk, chunk_id="chunk-2", document_id="doc-2")
    buffer = SentenceCitationBuffer([chunk, other])
    buffer.feed("Unsupported claim.")
    with pytest.raises(CitationValidationError, match="no citation"):
        buffer.finish()


def test_auto_cite_fills_uncited_scoped_multiple_contexts(chunk):
    other = replace(chunk, chunk_id="chunk-2", document_id="doc-2")
    buffer = SentenceCitationBuffer([chunk, other], auto_cite=True)
    buffer.feed("Rohan worked at Acme.")
    rendered = buffer.finish()
    assert rendered == ["Rohan worked at Acme. [1]"]
    assert buffer.citations()[0].chunk_id == "chunk-1"


def test_numbered_citation_maps_to_context_order(chunk):
    other = replace(chunk, chunk_id="chunk-2", document_id="doc-2")
    buffer = SentenceCitationBuffer([chunk, other])
    rendered = buffer.feed("Education details [1]. Work experience [2]. ")
    rendered += buffer.finish()
    assert rendered == ["Education details [1].", "Work experience [2]."]
    assert [citation.chunk_id for citation in buffer.citations()] == ["chunk-1", "chunk-2"]


def test_salvage_reparses_uncited_attached_answer(chunk):
    other = replace(chunk, chunk_id="chunk-2", document_id="doc-2")
    buffer = SentenceCitationBuffer([chunk, other])
    buffer.feed("Partial stream without markers")
    with pytest.raises(CitationValidationError):
        buffer.finish()
    rendered = buffer.salvage("Rohan worked at Acme. He led open source programs.")
    assert len(rendered) == 2
    assert all("[1]" in sentence for sentence in rendered)


def test_paragraph_citation_backfills_earlier_sentences(chunk):
    buffer = SentenceCitationBuffer([chunk])
    rendered = buffer.feed(
        "Rohan worked at Acme. He built backend systems. [C:chunk-1]. "
    )
    rendered += buffer.finish()
    assert len(rendered) >= 1
    assert all("[1]" in sentence for sentence in rendered)
    assert buffer.citations()[0].chunk_id == "chunk-1"


def test_paragraph_citation_backfills_on_stream(chunk):
    buffer = SentenceCitationBuffer([chunk])
    assert buffer.feed("First fact. Second fact. ") == []
    rendered = buffer.feed("More detail here. [C:chunk-1]. ")
    assert rendered
    assert all("[1]" in sentence for sentence in rendered)
