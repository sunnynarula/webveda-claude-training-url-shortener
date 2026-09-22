"""Error handling paths the acceptance tests don't reach."""

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.errors import PROBLEM_JSON, install_error_handlers
from app.middleware import CatchAllMiddleware, RequestIdMiddleware


def build() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)
    app.add_middleware(CatchAllMiddleware)
    app.add_middleware(RequestIdMiddleware)

    @app.get("/teapot")
    async def teapot() -> None:
        raise HTTPException(418, detail={"not": "a string"}, headers={"X-Extra": "1"})

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def body() -> AsyncIterator[bytes]:
            yield b"first chunk"
            raise RuntimeError("fails after the response started")

        return StreamingResponse(body())

    return app


async def test_unmapped_status_gets_a_generic_code_and_keeps_headers() -> None:
    transport = httpx.ASGITransport(app=build())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/teapot")
    assert response.status_code == 418
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.headers["x-extra"] == "1"
    body = response.json()
    assert body["code"] == "http_error"
    assert body["detail"] == "I'm a Teapot"


async def test_error_after_the_response_started_is_re_raised() -> None:
    # Headers are already sent, so a 500 can't replace them. The server must see the error.
    transport = httpx.ASGITransport(app=build())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        with pytest.raises(RuntimeError, match="after the response started"):
            await client.get("/stream")
