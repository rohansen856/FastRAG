from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sse_starlette.sse import EventSourceResponse

from . import __version__
from .admin import create_admin_router
from .bootstrap import build_pipeline
from .config import Settings, get_settings
from .domain import QueryRequest, QueryResponse
from .observability import observation
from .pipeline import PipelineUnavailable, QueryPipeline


def create_app(
    *, settings: Settings | None = None, pipeline: QueryPipeline | None = None
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
        app.state.ready = True
        yield
        app.state.ready = False

    app = FastAPI(title="FastRAG", version=__version__, lifespan=lifespan)
    app.state.ready = False

    async def require_query_key(authorization: str | None = Header(default=None)) -> None:
        _check_bearer(authorization, configured.query_api_key.get_secret_value())

    async def require_admin_key(authorization: str | None = Header(default=None)) -> None:
        _check_bearer(authorization, configured.admin_api_key.get_secret_value())

    def current_pipeline(request: Request) -> QueryPipeline:
        if not request.app.state.ready:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        return cast(QueryPipeline, request.app.state.pipeline)

    @app.post(
        "/v1/query",
        response_model=QueryResponse,
        dependencies=[Depends(require_query_key)],
    )
    async def query(body: QueryRequest, request: Request) -> QueryResponse:
        trace_id = uuid.uuid4().hex
        try:
            with observation(
                "rag-query",
                trace_id=trace_id,
                metadata={
                    "query_sha256": hashlib.sha256(body.query.encode()).hexdigest(),
                    "release": configured.release,
                    "environment": configured.environment,
                },
            ) as span:
                response = await current_pipeline(request).run(body.query, trace_id=trace_id)
                span.update(
                    output={
                        "outcome": response.outcome,
                        "citation_count": len(response.citations),
                    }
                )
                return response
        except PipelineUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"stage": exc.stage, "message": str(exc)},
            ) from exc

    @app.post("/v1/query/stream", dependencies=[Depends(require_query_key)])
    async def query_stream(body: QueryRequest, request: Request) -> EventSourceResponse:
        async def events() -> AsyncIterator[dict[str, str]]:
            trace_id = uuid.uuid4().hex
            try:
                with observation(
                    "rag-query",
                    trace_id=trace_id,
                    metadata={
                        "query_sha256": hashlib.sha256(body.query.encode()).hexdigest(),
                        "release": configured.release,
                        "environment": configured.environment,
                    },
                ) as span:
                    async for event in current_pipeline(request).stream(
                        body.query, trace_id=trace_id
                    ):
                        if event["event"] == "final":
                            span.update(output={"outcome": event["data"]["outcome"]})
                        yield {"event": event["event"], "data": json.dumps(event["data"])}
            except PipelineUnavailable as exc:
                yield {
                    "event": "error",
                    "data": json.dumps({"stage": exc.stage, "message": str(exc)}),
                }

        return EventSourceResponse(events())

    @app.get("/health/live", include_in_schema=False)
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", include_in_schema=False)
    async def ready(request: Request) -> JSONResponse:
        code = 200 if request.app.state.ready else 503
        return JSONResponse({"status": "ready" if code == 200 else "not_ready"}, code)

    @app.get("/build", dependencies=[Depends(require_admin_key)])
    async def build() -> dict[str, str]:
        return {"version": __version__, "release": configured.release}

    @app.get("/metrics", include_in_schema=False)
    async def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    app.include_router(create_admin_router(configured, require_admin_key))

    return app


def _check_bearer(authorization: str | None, expected: str) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token")
    supplied = authorization.removeprefix("Bearer ")
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="invalid bearer token")


app = create_app()
