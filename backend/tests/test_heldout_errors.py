"""Held-out tests for the error shape (TASKS.md slice 1, acceptance 6; ADR 0002).

ADR 0002 says *every* error is `application/problem+json` with `type`, `title`, `status`,
`detail`, `code` and `request_id`, and that a 422 never echoes input. The acceptance tests
walk the four error paths the contract names. These walk the ones a client can reach without
a route handler being involved at all: a HEAD request, a preflight, a trailing slash, a body
sent to a route that takes none.

Three tests from this file are deliberately absent, along with their probe routes. They fail
by decision rather than by accident, and each is an open issue carrying the evidence: a
refused CORS preflight is answered in plain text by CORSMiddleware (#9), a 422 reflects the
field name a client invented (#14, settled in slice 3), and an HTTPException with a status
outside http.HTTPStatus becomes a 500 (#13, slice 6).
"""

import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app

HEALTH = "/api/health/live"
PROBLEM_MEMBERS = {"type", "title", "status", "detail", "code", "request_id"}
ALLOWED_ORIGIN = "http://localhost:5173"


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """Overrides conftest's ``app``. The probe routes went with the three tests that are
    held back for #9, #13 and #14; what is left needs no route of its own."""
    return create_app(settings)


def assert_problem(response: httpx.Response, status: int) -> dict[str, Any]:
    """The shape every error shares, checked without naming a code."""
    assert response.status_code == status, response.text
    media_type = response.headers.get("content-type", "").split(";")[0].strip()
    assert media_type == "application/problem+json", f"{media_type!r}: {response.text!r}"
    body = response.json()
    assert isinstance(body, dict), body
    assert PROBLEM_MEMBERS <= body.keys(), f"missing {sorted(PROBLEM_MEMBERS - body.keys())}"
    assert body["status"] == status
    assert body["code"], body
    assert body["request_id"] == response.headers.get("x-request-id")
    return body


async def test_head_on_a_get_route_is_answered(client: httpx.AsyncClient) -> None:
    """RFC 9110 §9.1: a general-purpose server supports GET and HEAD everywhere it supports
    GET. Monitors and link checkers send HEAD, and CLAUDE.md §6 needs it for the redirect in
    slice 4, so the health route is where the behaviour shows up first."""
    response = await client.head(HEALTH)

    assert response.status_code == 200, f"HEAD {HEALTH} -> {response.status_code}"
    assert response.headers.get("x-request-id"), "no X-Request-ID header"


async def test_head_on_an_unknown_route_still_carries_the_problem_headers(
    client: httpx.AsyncClient,
) -> None:
    """A HEAD response has no body, so the status, the content type and the request ID are
    all the client gets. They still have to be the problem+json ones."""
    response = await client.head("/api/no-such/route")

    assert response.status_code == 404
    media_type = response.headers.get("content-type", "").split(";")[0].strip()
    assert media_type == "application/problem+json", media_type
    assert response.headers.get("x-request-id"), "no X-Request-ID header"
    assert response.content == b"", response.content


@pytest.mark.parametrize(
    "method", [pytest.param("PATCH", id="patch"), pytest.param("DELETE", id="delete")]
)
async def test_an_unsupported_method_is_a_problem_naming_what_is_allowed(
    client: httpx.AsyncClient, method: str
) -> None:
    """RFC 9110 §15.5.6: a 405 MUST carry `Allow`. Without it a client has to guess."""
    response = await client.request(method, HEALTH)

    body = assert_problem(response, 405)
    assert body["code"] == "method_not_allowed"
    allow = response.headers.get("allow")
    assert allow, "a 405 without an Allow header"
    assert "GET" in allow, allow


async def test_a_preflight_the_frontend_needs_is_allowed(client: httpx.AsyncClient) -> None:
    """The mirror of the test above: the origin in the settings really is allowed, so a
    failure there is about the refusal path and not about CORS being broken outright."""
    response = await client.request(
        "OPTIONS",
        HEALTH,
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Request-ID",
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("GET", HEALTH, id="ok"),
        pytest.param("GET", "/api/no-such/route", id="not-found"),
        pytest.param("POST", HEALTH, id="method-not-allowed"),
    ],
)
async def test_an_unknown_origin_is_never_reflected(
    client: httpx.AsyncClient, method: str, path: str
) -> None:
    """`allow_origins=[FRONTEND_ORIGIN]`, never `*` and never the caller's own origin
    (CLAUDE.md §10). A reflected origin would hand any site the API."""
    origin = f"https://evil-{uuid.uuid4().hex[:8]}.example"

    response = await client.request(method, path, headers={"Origin": origin})

    allowed = response.headers.get("access-control-allow-origin")
    assert allowed != origin, response.headers
    assert allowed in {None, ALLOWED_ORIGIN}, allowed


async def test_an_allowed_origin_response_varies_on_origin(client: httpx.AsyncClient) -> None:
    """A single-origin CORS response is not cacheable across origins unless it says so."""
    response = await client.get(HEALTH, headers={"Origin": ALLOWED_ORIGIN})

    assert response.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert "origin" in response.headers.get("vary", "").lower(), response.headers


async def test_the_router_does_not_echo_client_input_into_a_redirect(
    client: httpx.AsyncClient,
) -> None:
    """A trailing slash makes the router answer with a 307 of its own, before any route code
    runs. Its `Location` is built from the request, so the query string the access log is
    careful never to record, and the Host header the client chose, both come straight back.
    Slice 4 puts `/{short_code}` at the root, where this route matches almost anything."""
    marker = f"marker{uuid.uuid4().hex}"

    response = await client.get(
        f"{HEALTH}/?leak={marker}",
        headers={"Host": "attacker.example"},
        follow_redirects=False,
    )

    location = response.headers.get("location", "")
    assert marker not in location, location
    assert "attacker.example" not in location, location


async def test_an_unknown_route_with_a_trailing_slash_is_still_a_problem(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/no-such/route/", follow_redirects=False)

    body = assert_problem(response, 404)
    assert body["code"] == "not_found"


async def test_a_body_sent_to_a_route_that_takes_none_is_ignored_not_echoed(
    client: httpx.AsyncClient,
) -> None:
    """GET with a body is legal on the wire. Whatever the app does with it, the body must not
    come back."""
    marker = f"marker{uuid.uuid4().hex}"

    response = await client.request(
        "GET",
        HEALTH,
        content=f'{{"leak": "{marker}"}}'.encode(),
        headers={"Content-Type": "application/json"},
    )

    assert marker not in response.text, response.text
    assert response.status_code == 200, response.text
