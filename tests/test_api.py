import httpx
import pytest
from conftest import make_pipeline
from pydantic import SecretStr

from fastrag.api import create_app
from fastrag.config import Settings


@pytest.mark.asyncio
async def test_query_endpoint_requires_and_accepts_bearer_key(chunk):
    pipeline, _ = make_pipeline(chunk)
    settings = Settings(
        query_api_key=SecretStr("query-secret"),
        admin_api_key=SecretStr("admin-secret"),
    )
    app = create_app(settings=settings, pipeline=pipeline)
    app.state.pipeline = pipeline
    app.state.ready = True
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.post("/v1/query", json={"query": "refund"})).status_code == 401
        response = await client.post(
            "/v1/query",
            headers={"Authorization": "Bearer query-secret"},
            json={"query": "refund"},
        )
    assert response.status_code == 200
    assert response.json()["outcome"] == "answered"
    assert response.json()["citations"][0]["chunk_id"] == "chunk-1"
