from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, cast

import anyio.to_thread
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette.sse import EventSourceResponse

from . import __version__
from .admin import create_admin_router
from .bootstrap import build_pipeline, build_transcriber
from .chunking import STRATEGY_NAMES
from .config import Settings, get_settings
from .domain import QueryRequest, QueryResponse, Transcript
from .harness import Deadline, ProviderError
from .observability import observation
from .pipeline import PipelineUnavailable, QueryPipeline
from .ports import Transcriber

BENCH_REPORT_PATH = Path("bench/results/summary.json")

AudioUpload = Annotated[UploadFile, File(description="Recorded question audio")]
OptionalForm = Annotated[str | None, Form()]


def create_app(
    *,
    settings: Settings | None = None,
    pipeline: QueryPipeline | None = None,
    transcriber: Transcriber | None = None,
) -> FastAPI:
    configured = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if pipeline is None:
            built_pipeline, cache = await build_pipeline(configured)
            app.state.pipeline = built_pipeline
            app.state.cache = cache
        else:
            app.state.pipeline = pipeline
        app.state.transcriber = transcriber or build_transcriber(configured)
        app.state.ready = True
        yield
        app.state.ready = False

    app = FastAPI(title="FastRAG", version=__version__, lifespan=lifespan)
    app.state.ready = False
    app.state.transcriber = transcriber

    # The voice UI is deployed separately on Vercel, so it is always cross-origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=configured.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    async def require_query_key(authorization: str | None = Header(default=None)) -> None:
        _check_bearer(authorization, configured.query_api_key.get_secret_value())

    async def require_admin_key(authorization: str | None = Header(default=None)) -> None:
        _check_bearer(authorization, configured.admin_api_key.get_secret_value())

    def current_pipeline(request: Request) -> QueryPipeline:
        if not request.app.state.ready:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        return cast(QueryPipeline, request.app.state.pipeline)

    def current_transcriber(request: Request) -> Transcriber:
        candidate = getattr(request.app.state, "transcriber", None)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"stage": "stt", "message": "no speech-to-text provider is configured"},
            )
        return cast(Transcriber, candidate)

    async def read_audio(file: UploadFile) -> bytes:
        audio = await file.read()
        if not audio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="empty audio upload"
            )
        if len(audio) > configured.stt_max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"audio exceeds {configured.stt_max_bytes} bytes",
            )
        return audio

    def trace_metadata(text: str) -> dict[str, str]:
        return {
            "query_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "release": configured.release,
            "environment": configured.environment,
            "profile": configured.profile,
        }

    @app.post(
        "/v1/query",
        response_model=QueryResponse,
        dependencies=[Depends(require_query_key)],
    )
    async def query(body: QueryRequest, request: Request) -> QueryResponse:
        trace_id = uuid.uuid4().hex
        try:
            with observation("rag-query", trace_id=trace_id, metadata=trace_metadata(body.query)):
                return await current_pipeline(request).run(
                    body.query,
                    trace_id=trace_id,
                    strategy=body.strategy,
                    language=body.language,
                )
        except PipelineUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"stage": exc.stage, "message": str(exc)},
            ) from exc

    @app.post("/v1/query/stream", dependencies=[Depends(require_query_key)])
    async def query_stream(body: QueryRequest, request: Request) -> EventSourceResponse:
        pipeline_ref = current_pipeline(request)
        return EventSourceResponse(
            _stream_events(
                pipeline_ref,
                body.query,
                metadata=trace_metadata(body.query),
                strategy=body.strategy,
                language=body.language,
            )
        )

    @app.post("/v1/transcribe", dependencies=[Depends(require_query_key)])
    async def transcribe(
        request: Request,
        file: AudioUpload,
        language: OptionalForm = None,
    ) -> Transcript:
        audio = await read_audio(file)
        try:
            return await current_transcriber(request).transcribe(
                audio,
                filename=file.filename or "audio.wav",
                language=language,
                deadline=Deadline(configured.stt_timeout_seconds),
            )
        except ProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"stage": "stt", "message": str(exc)},
            ) from exc

    @app.post(
        "/v1/voice/query",
        response_model=QueryResponse,
        dependencies=[Depends(require_query_key)],
    )
    async def voice_query(
        request: Request,
        file: AudioUpload,
        language: OptionalForm = None,
        strategy: OptionalForm = None,
    ) -> QueryResponse:
        audio = await read_audio(file)
        trace_id = uuid.uuid4().hex
        try:
            transcript = await current_transcriber(request).transcribe(
                audio,
                filename=file.filename or "audio.wav",
                language=language,
                deadline=Deadline(configured.stt_timeout_seconds),
            )
            with observation(
                "voice-query", trace_id=trace_id, metadata=trace_metadata(transcript.text)
            ):
                return await current_pipeline(request).run(
                    transcript.text,
                    trace_id=trace_id,
                    strategy=strategy,
                    language=language,
                    transcript=transcript,
                )
        except ProviderError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"stage": "stt", "message": str(exc)},
            ) from exc
        except PipelineUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"stage": exc.stage, "message": str(exc)},
            ) from exc

    @app.post("/v1/voice/query/stream", dependencies=[Depends(require_query_key)])
    async def voice_query_stream(
        request: Request,
        file: AudioUpload,
        language: OptionalForm = None,
        strategy: OptionalForm = None,
    ) -> EventSourceResponse:
        audio = await read_audio(file)
        speech = current_transcriber(request)
        pipeline_ref = current_pipeline(request)
        filename = file.filename or "audio.wav"

        async def events() -> AsyncIterator[dict[str, str]]:
            try:
                transcript = await speech.transcribe(
                    audio,
                    filename=filename,
                    language=language,
                    deadline=Deadline(configured.stt_timeout_seconds),
                )
            except ProviderError as exc:
                yield {
                    "event": "error",
                    "data": json.dumps({"stage": "stt", "message": str(exc)}),
                }
                return
            yield {"event": "transcript", "data": transcript.model_dump_json()}
            async for event in _stream_events(
                pipeline_ref,
                transcript.text,
                metadata=trace_metadata(transcript.text),
                strategy=strategy,
                language=language,
                transcript=transcript,
            ):
                yield event

        return EventSourceResponse(events())

    @app.get("/v1/strategies", dependencies=[Depends(require_query_key)])
    async def strategies() -> dict[str, object]:
        return {
            "available": list(STRATEGY_NAMES),
            "indexed": configured.chunk_strategy_list,
            "default": (configured.chunk_strategy_list or ["sentence"])[0],
        }

    @app.get("/v1/bench", dependencies=[Depends(require_query_key)])
    async def bench() -> JSONResponse:
        report = await anyio.to_thread.run_sync(_read_bench_report)
        if report is None:
            return JSONResponse({"detail": "no benchmark report available"}, 404)
        return JSONResponse(report)

    @app.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def ready(request: Request) -> JSONResponse:
        code = 200 if request.app.state.ready else 503
        return JSONResponse({"status": "ready" if code == 200 else "not_ready"}, code)

    @app.get("/build", dependencies=[Depends(require_admin_key)])
    async def build() -> dict[str, str]:
        return {
            "version": __version__,
            "release": configured.release,
            "profile": configured.profile,
            "embedding_provider": configured.active_embedding_provider,
            "reranker_provider": configured.active_reranker_provider,
            "stt_provider": configured.active_stt_provider,
        }

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(create_admin_router(configured, require_admin_key))

    return app


def _read_bench_report() -> dict[str, object] | None:
    if not BENCH_REPORT_PATH.is_file():
        return None
    try:
        report: dict[str, object] = json.loads(BENCH_REPORT_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return report


async def _stream_events(
    pipeline: QueryPipeline,
    query: str,
    *,
    metadata: dict[str, str],
    strategy: str | None = None,
    language: str | None = None,
    transcript: Transcript | None = None,
) -> AsyncIterator[dict[str, str]]:
    trace_id = uuid.uuid4().hex
    try:
        with observation("rag-query", trace_id=trace_id, metadata=metadata) as span:
            async for event in pipeline.stream(
                query,
                trace_id=trace_id,
                strategy=strategy,
                language=language,
                transcript=transcript,
            ):
                if event["event"] == "final":
                    span.update(output={"outcome": event["data"]["outcome"]})
                yield {"event": event["event"], "data": json.dumps(event["data"])}
    except PipelineUnavailable as exc:
        yield {
            "event": "error",
            "data": json.dumps({"stage": exc.stage, "message": str(exc)}),
        }


def _check_bearer(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    supplied = authorization.removeprefix("Bearer ")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid bearer token")


app = create_app()
