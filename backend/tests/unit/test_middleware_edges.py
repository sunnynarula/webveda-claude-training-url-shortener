"""Middleware paths the acceptance and held-out tests don't reach."""

from collections.abc import AsyncIterator

import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from app.middleware import HeadAsGetMiddleware


async def test_head_drops_every_chunk_of_a_streaming_response() -> None:
    """A streaming response sends many body messages. HEAD must answer with the headers
    and nothing else, so the chunks after the first are dropped rather than sent."""
    app = FastAPI()
    app.add_middleware(HeadAsGetMiddleware)

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        async def body() -> AsyncIterator[bytes]:
            yield b"one"
            yield b"two"

        return StreamingResponse(body(), media_type="text/plain")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        head = await client.head("/stream")
        get = await client.get("/stream")

    assert head.status_code == 200
    assert head.content == b""
    assert get.content == b"onetwo"
    assert head.headers["content-type"] == get.headers["content-type"]


async def test_a_websocket_scope_passes_straight_through() -> None:
    """Only http scopes are rewritten; anything else is handed on untouched."""
    seen: list[str] = []

    async def app(scope, receive, send):
        seen.append(str(scope["type"]))

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        return None

    await HeadAsGetMiddleware(app)({"type": "websocket"}, receive, send)

    assert seen == ["websocket"]
