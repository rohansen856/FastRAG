"""Speech-to-text adapters.

Sarvam's Saaras v3 is the default because the corpus is Indic: it covers 22
Indian languages and code-mixed speech, which the ElevenLabs and Whisper-class
models handle noticeably worse for Hindi/Bengali/Tamil/Telugu/Marathi audio.
"""

from __future__ import annotations

import time

import httpx

from ..domain import Transcript
from ..harness import Deadline, ProviderError, ProviderHarness

SARVAM = "sarvam"
ELEVENLABS = "elevenlabs"

# Saaras wants BCP-47 regional tags; the rest of FastRAG uses ISO 639-1.
_SARVAM_LANGUAGE = {
    "en": "en-IN",
    "hi": "hi-IN",
    "bn": "bn-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "mr": "mr-IN",
}


class TranscriptionError(ProviderError):
    pass


class SarvamTranscriber:
    """Sarvam Saaras v3 speech-to-text.

    Authentication uses the `api-subscription-key` header, not a bearer token.
    The synchronous endpoint caps audio at 30 seconds.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.sarvam.ai",
        model: str = "saaras:v3",
        mode: str = "transcribe",
        timeout_seconds: float = 20.0,
        harness: ProviderHarness | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/speech-to-text"
        self._model = model
        self._mode = mode
        self._harness = harness or ProviderHarness(SARVAM)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds)),
            headers={"api-subscription-key": api_key},
        )

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "audio.wav",
        language: str | None = None,
        deadline: Deadline | None = None,
    ) -> Transcript:
        started = time.perf_counter()
        data = {"model": self._model, "mode": self._mode}
        if language:
            data["language_code"] = _SARVAM_LANGUAGE.get(language.casefold(), language)

        async def call() -> dict[str, object]:
            response = await self._client.post(
                self._url,
                data=data,
                files={"file": (filename, audio, "audio/wav")},
            )
            response.raise_for_status()
            body: dict[str, object] = response.json()
            return body

        body = await self._harness.call(call, stage="stt", deadline=deadline)
        text = str(body.get("transcript") or "").strip()
        if not text:
            raise TranscriptionError(SARVAM, "transcription returned no text")
        return Transcript(
            text=text,
            language_code=(str(body["language_code"]) if body.get("language_code") else None),
            provider=SARVAM,
            model=self._model,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    async def aclose(self) -> None:
        await self._client.aclose()


class ElevenLabsTranscriber:
    """ElevenLabs Scribe speech-to-text."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.elevenlabs.io/v1",
        model: str = "scribe_v1",
        timeout_seconds: float = 20.0,
        harness: ProviderHarness | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/speech-to-text"
        self._model = model
        self._harness = harness or ProviderHarness(ELEVENLABS)
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds, connect=min(5.0, timeout_seconds)),
            headers={"xi-api-key": api_key},
        )

    async def transcribe(
        self,
        audio: bytes,
        *,
        filename: str = "audio.wav",
        language: str | None = None,
        deadline: Deadline | None = None,
    ) -> Transcript:
        started = time.perf_counter()
        data = {"model_id": self._model}
        if language:
            data["language_code"] = language

        async def call() -> dict[str, object]:
            response = await self._client.post(
                self._url,
                data=data,
                files={"file": (filename, audio, "audio/wav")},
            )
            response.raise_for_status()
            body: dict[str, object] = response.json()
            return body

        body = await self._harness.call(call, stage="stt", deadline=deadline)
        text = str(body.get("text") or "").strip()
        if not text:
            raise TranscriptionError(ELEVENLABS, "transcription returned no text")
        return Transcript(
            text=text,
            language_code=(str(body["language_code"]) if body.get("language_code") else None),
            provider=ELEVENLABS,
            model=self._model,
            duration_ms=(time.perf_counter() - started) * 1000,
        )

    async def aclose(self) -> None:
        await self._client.aclose()
