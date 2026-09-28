"""Unreadable audio is the caller's error; a broken provider is ours."""

from __future__ import annotations

import httpx
import pytest
from conftest import make_pipeline
from pydantic import SecretStr

from fastrag.api import create_app
from fastrag.config import Settings
from fastrag.harness import ProviderError


class _FailingTranscriber:
    def __init__(self, status_code: int | None) -> None:
        self.status_code = status_code

    async def transcribe(self, audio: bytes, **_: object) -> object:
        raise ProviderError(
            "sarvam", f"sarvam returned {self.status_code}", status_code=self.status_code
        )


async def _post(chunk, status_code: int | None, path: str) -> httpx.Response:
    pipeline, _ = make_pipeline(chunk)
    app = create_app(
        settings=Settings(query_api_key=SecretStr("k")),
        pipeline=pipeline,
        transcriber=_FailingTranscriber(status_code),
    )
    app.state.pipeline = pipeline
    app.state.transcriber = _FailingTranscriber(status_code)
    app.state.ready = True
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        return await c.post(
            path,
            headers={"Authorization": "Bearer k"},
            files={"file": ("a.wav", b"RIFF-not-really-audio", "audio/wav")},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["/v1/transcribe", "/v1/voice/query"])
@pytest.mark.parametrize(
    ("provider_status", "expected"), [(400, 422), (415, 422), (401, 503), (500, 503), (None, 503)]
)
async def test_stt_errors_are_attributed_to_the_right_side(chunk, path, provider_status, expected):
    response = await _post(chunk, provider_status, path)
    assert response.status_code == expected
    assert response.json()["detail"]["stage"] == "stt"
