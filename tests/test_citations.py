import pytest

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


def test_rejects_unknown_citation(chunk):
    buffer = SentenceCitationBuffer([chunk])
    with pytest.raises(CitationValidationError, match="unknown citation"):
        buffer.feed("Unsupported claim [C:made-up]. ")
        buffer.finish()


def test_rejects_uncited_sentence(chunk):
    buffer = SentenceCitationBuffer([chunk])
    with pytest.raises(CitationValidationError, match="no citation"):
        buffer.feed("Unsupported claim. ")
        buffer.finish()
