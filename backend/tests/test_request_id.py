"""Acceptance test 5 (TASKS.md, slice 1; CLAUDE.md §9): X-Request-ID is accepted only if it
matches ``^[A-Za-z0-9._-]{1,64}$``, is otherwise replaced with a uuid4 hex, and is always
echoed."""

import asyncio
import re
import uuid

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app

HEALTH = "/api/health/live"
SLOW_ROUTE = "/__probe__/slow"


async def slow() -> dict[str, str]:
    await asyncio.sleep(0.05)
    return {"status": "ok"}


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """Overrides conftest's ``app``: the real app plus a route that stays in flight.

    The liveness route never waits on anything, so requests sent to it together still run one
    after another, and a request ID shared between requests would go unnoticed. Requests to the
    slow route overlap, which is what the concurrency test needs.
    """
    application = create_app(settings)
    application.add_api_route(SLOW_ROUTE, slow, methods=["GET"])
    return application


def assert_generated(request_id: str | None) -> None:
    assert request_id is not None, "no X-Request-ID header"
    assert re.fullmatch(r"[0-9a-f]{32}", request_id), f"not a uuid4 hex: {request_id!r}"
    assert uuid.UUID(hex=request_id).version == 4, f"not a uuid4: {request_id!r}"


async def test_missing_request_id_is_generated_per_request(client: httpx.AsyncClient) -> None:
    first = await client.get(HEALTH)
    second = await client.get(HEALTH)

    assert_generated(first.headers.get("x-request-id"))
    assert_generated(second.headers.get("x-request-id"))
    assert first.headers["x-request-id"] != second.headers["x-request-id"]


@pytest.mark.parametrize(
    "incoming",
    [
        pytest.param("bad id!", id="space-and-bang"),
        pytest.param("a" * 65, id="65-chars"),
        pytest.param("", id="empty"),
    ],
)
async def test_malformed_request_id_is_replaced(client: httpx.AsyncClient, incoming: str) -> None:
    response = await client.get(HEALTH, headers={"X-Request-ID": incoming})

    returned = response.headers.get("x-request-id")
    assert returned != incoming
    assert_generated(returned)


@pytest.mark.parametrize(
    "incoming",
    [
        pytest.param("abc-123", id="simple"),
        pytest.param("Req.2026_09-22", id="every-allowed-punctuation"),
        pytest.param("a" * 64, id="64-chars"),
    ],
)
async def test_valid_request_id_is_echoed(client: httpx.AsyncClient, incoming: str) -> None:
    response = await client.get(HEALTH, headers={"X-Request-ID": incoming})

    assert response.headers.get("x-request-id") == incoming


async def test_concurrent_requests_each_get_their_own_request_id(
    client: httpx.AsyncClient,
) -> None:
    sent = [f"concurrent-{i:02d}-{uuid.uuid4().hex[:8]}" for i in range(20)]

    responses = await asyncio.gather(
        *(client.get(SLOW_ROUTE, headers={"X-Request-ID": request_id}) for request_id in sent)
    )

    assert [response.headers.get("x-request-id") for response in responses] == sent
