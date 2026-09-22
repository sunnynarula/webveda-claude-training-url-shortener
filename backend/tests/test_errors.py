"""Acceptance test 6 (TASKS.md, slice 1; ADR 0002): every error has one RFC 9457 shape.

Slice 1 has no real route that takes a body or fails, so this module's ``app`` fixture adds
two probe routes to the app before the client starts.
"""

import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from app.config import Settings
from app.main import create_app

PROBLEM_MEMBERS = {"type", "title", "status", "detail", "code", "request_id"}
BODY_ROUTE = "/__probe__/body"
RAISE_ROUTE = "/__probe__/raise"
# The probe route raises with this text. A 500 must not show it to the client.
EXCEPTION_TEXT = f"probe-exception-{uuid.uuid4().hex}"


class ProbeBody(BaseModel):
    name: str
    quantity: int


async def accept_body(body: ProbeBody) -> dict[str, str]:
    return {"name": body.name}


async def always_raise() -> None:
    raise RuntimeError(EXCEPTION_TEXT)


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """Overrides conftest's ``app``: the real app plus the two probe routes."""
    application = create_app(settings)
    application.add_api_route(BODY_ROUTE, accept_body, methods=["POST"])
    application.add_api_route(RAISE_ROUTE, always_raise, methods=["GET"])
    return application


def assert_problem(response: httpx.Response, status: int, code: str) -> dict[str, Any]:
    """Check the problem+json shape shared by every error, and return the body."""
    assert response.status_code == status, response.text
    media_type = response.headers.get("content-type", "").split(";")[0].strip()
    assert media_type == "application/problem+json", f"{media_type!r}: {response.text}"
    body = response.json()
    assert isinstance(body, dict), body
    assert PROBLEM_MEMBERS <= body.keys(), f"missing {sorted(PROBLEM_MEMBERS - body.keys())}"
    assert body["code"] == code
    assert body["status"] == status
    assert isinstance(body["type"], str) and body["type"]
    assert isinstance(body["title"], str) and body["title"]
    assert isinstance(body["detail"], str)
    header_id = response.headers.get("x-request-id")
    assert header_id, "no X-Request-ID header"
    assert body["request_id"] == header_id
    return body


def assert_errors_listed(body: dict[str, Any]) -> list[dict[str, Any]]:
    """A 422 lists the problems as {loc, msg, type}, and nothing else (no ``input``)."""
    errors = body.get("errors")
    assert isinstance(errors, list) and errors, f"no errors listed: {body}"
    for error in errors:
        assert isinstance(error, dict) and set(error) == {"loc", "msg", "type"}, error
    return errors


async def test_unknown_route_is_404_not_found(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/no-such/route")

    assert_problem(response, 404, "not_found")


async def test_wrong_method_is_405_method_not_allowed(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/health/live")

    assert_problem(response, 405, "method_not_allowed")


async def test_bad_json_is_422_invalid_request_without_echoing_input(
    client: httpx.AsyncClient,
) -> None:
    marker = f"marker-{uuid.uuid4().hex}"

    response = await client.post(
        BODY_ROUTE,
        content=f'{{"name": "{marker}", "quantity": '.encode(),
        headers={"Content-Type": "application/json"},
    )

    body = assert_problem(response, 422, "invalid_request")
    assert_errors_listed(body)
    assert marker not in response.text


async def test_wrongly_typed_body_is_422_invalid_request_without_echoing_input(
    client: httpx.AsyncClient,
) -> None:
    marker = f"marker-{uuid.uuid4().hex}"

    response = await client.post(BODY_ROUTE, json={"name": "probe", "quantity": marker})

    body = assert_problem(response, 422, "invalid_request")
    errors = assert_errors_listed(body)
    assert any(error["loc"][-1] == "quantity" for error in errors), errors
    assert marker not in response.text


async def test_unhandled_exception_is_500_internal_error_with_cors_and_request_id(
    client: httpx.AsyncClient, settings_values: dict[str, str]
) -> None:
    origin = settings_values["frontend_origin"]
    request_id = f"forced-500-{uuid.uuid4().hex[:12]}"

    response = await client.get(RAISE_ROUTE, headers={"Origin": origin, "X-Request-ID": request_id})

    body = assert_problem(response, 500, "internal_error")
    assert body["request_id"] == request_id
    assert response.headers.get("access-control-allow-origin") == origin
    assert EXCEPTION_TEXT not in response.text
