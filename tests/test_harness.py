import httpx

from fastrag.harness import classify


def test_classify_includes_the_response_body() -> None:
    """A bare status code turns an actionable provider message into a mystery."""
    request = httpx.Request("POST", "https://example.invalid/v1/chat/completions")
    response = httpx.Response(
        400, request=request, json={"error": {"message": "Request too large for model"}}
    )
    error = classify("generator", httpx.HTTPStatusError("x", request=request, response=response))
    assert error.status_code == 400
    assert not error.retryable
    assert "Request too large for model" in str(error)


def test_classify_marks_rate_limits_retryable() -> None:
    request = httpx.Request("POST", "https://example.invalid/v1/embeddings")
    response = httpx.Response(429, request=request, text="slow down")
    error = classify("jina", httpx.HTTPStatusError("x", request=request, response=response))
    assert error.retryable
    assert "slow down" in str(error)
