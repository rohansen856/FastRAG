import pytest

from fastrag.citations import CitationValidationError, SentenceCitationBuffer


def test_validates_and_numbers_citations(chunk):
    buffer = SentenceCitationBuffer([chunk])
    rendered = buffer.feed("Refunds last thirty days [C:chunk-1]. ")
    assert rendered == ["Refunds last thirty days [1]."]
    assert buffer.citations()[0].chunk_id == "chunk-1"


def test_rejects_unknown_citation(chunk):
    buffer = SentenceCitationBuffer([chunk])
    with pytest.raises(CitationValidationError, match="unknown citation"):
        buffer.feed("Unsupported claim [C:made-up]. ")


def test_rejects_uncited_sentence(chunk):
    buffer = SentenceCitationBuffer([chunk])
    with pytest.raises(CitationValidationError, match="no citation"):
        buffer.feed("Unsupported claim. ")
