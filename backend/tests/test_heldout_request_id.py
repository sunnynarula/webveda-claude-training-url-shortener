"""Held-out tests for X-Request-ID (TASKS.md slice 1, acceptance 5; CLAUDE.md §9).

The contract: an incoming ``X-Request-ID`` is kept only when it matches
``^[A-Za-z0-9._-]{1,64}$``; anything else is replaced with a uuid4 hex; the ID is *always*
echoed in the response.

These tests reach the middleware through a hand-built ASGI scope as well as through httpx.
An HTTP client sanitises header values before they leave the process, so a client-driven test
can never show what the middleware does with a raw byte string that carries CR, LF, NUL or a
non-ASCII byte -- which is exactly the input a hostile proxy hop can deliver.
"""

import asyncio
import re
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import Settings
from app.main import create_app
from app.request_context import current_request_id

HEALTH = "/api/health/live"
SLOW_ROUTE = "/__heldout__/slow"
GENERATED = re.compile(r"[0-9a-f]{32}")
ALLOWED_BYTES = re.compile(rb"[A-Za-z0-9._-]{1,64}")


async def slow() -> dict[str, str]:
    """A route that stays in flight, so concurrent requests really do overlap."""
    await asyncio.sleep(0.05)
    return {"status": "ok"}


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    """Overrides conftest's ``app``: the real app plus one slow route."""
    application = create_app(settings)
    application.add_api_route(SLOW_ROUTE, slow, methods=["GET"])
    return application


async def response_headers(
    app: FastAPI,
    headers: Iterable[tuple[bytes, bytes]],
    *,
    method: str = "GET",
    path: str = HEALTH,
) -> list[tuple[bytes, bytes]]:
    """Call the ASGI app directly with raw header bytes and return the response headers.

    Nothing between the test and the middleware normalises or rejects the bytes, which is the
    point: this is what an upstream hop can hand to uvicorn.
    """
    scope: dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "root_path": "",
        "headers": list(headers),
        "client": ("127.0.0.1", 45678),
        "server": ("testserver", 80),
    }
    messages: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        messages.append(message)

    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    return [(bytes(key), bytes(value)) for key, value in start["headers"]]


def echoed(headers: Sequence[tuple[bytes, bytes]]) -> bytes:
    """The single echoed request ID. Two of them would let a client and the server disagree
    about which ID names the request."""
    values = [value for key, value in headers if key.lower() == b"x-request-id"]
    assert len(values) == 1, f"want exactly one X-Request-ID header, got {values}"
    return values[0]


# Values a client library would refuse to send, or would quietly rewrite, but that a proxy
# hop or a hand-rolled ASGI server can deliver unchanged.
SMUGGLING_ATTEMPTS = [
    pytest.param(b"good\r\nX-Evil: injected", id="crlf-header-injection"),
    pytest.param(b"good\nX-Evil: injected", id="lf-header-injection"),
    pytest.param(b"good\rX-Evil: injected", id="cr-header-injection"),
    pytest.param(b"good\x00evil", id="nul-byte"),
    pytest.param(b"good evil", id="space"),
    pytest.param(b"good\tevil", id="tab"),
    pytest.param(b" good", id="leading-space"),
    pytest.param(b"good ", id="trailing-space"),
    pytest.param(b"first-id, second-id", id="proxy-folded-duplicates"),
    pytest.param(b"caf\xe9", id="non-ascii-latin1"),
    pytest.param("café".encode(), id="non-ascii-utf8"),
    pytest.param(b'{"level":"CRITICAL"}', id="json-log-injection"),
    pytest.param(b"../../etc/passwd", id="path-traversal"),
    pytest.param(b"<script>alert(1)</script>", id="html"),
    pytest.param(b"a" * 65, id="65-chars"),
    pytest.param(b"a" * 4096, id="4096-chars"),
    pytest.param(b"", id="empty"),
    pytest.param(b"good\n", id="trailing-newline"),
]


@pytest.mark.parametrize("incoming", SMUGGLING_ATTEMPTS)
async def test_a_raw_request_id_that_is_not_in_the_charset_is_replaced(
    app: FastAPI, incoming: bytes
) -> None:
    headers = await response_headers(app, [(b"x-request-id", incoming)])

    returned = echoed(headers)
    assert returned != incoming
    assert ALLOWED_BYTES.fullmatch(returned), f"echoed an out-of-charset ID: {returned!r}"
    assert GENERATED.fullmatch(returned.decode("ascii")), f"not a uuid4 hex: {returned!r}"
    assert not any(key.lower() == b"x-evil" for key, _ in headers), headers
    for key, value in headers:
        assert b"\r" not in key + value and b"\n" not in key + value, (key, value)


@pytest.mark.parametrize(
    "incoming",
    [
        pytest.param(b"a", id="1-char"),
        pytest.param(b"-", id="only-hyphen"),
        pytest.param(b".", id="only-dot"),
        pytest.param(b"_", id="only-underscore"),
        pytest.param(b"0", id="only-digit"),
        pytest.param(b"a" * 64, id="64-chars"),
        pytest.param(b"-" * 64, id="64-hyphens"),
        pytest.param(b"..", id="dot-dot"),
        pytest.param(b"0123456789abcdefABCDEF._-", id="whole-charset"),
    ],
)
async def test_a_raw_request_id_inside_the_charset_is_echoed_unchanged(
    app: FastAPI, incoming: bytes
) -> None:
    headers = await response_headers(app, [(b"x-request-id", incoming)])

    assert echoed(headers) == incoming


async def test_the_header_name_is_matched_case_insensitively(app: FastAPI) -> None:
    """ASGI servers are told to lowercase header names, but not every one does."""
    headers = await response_headers(app, [(b"X-Request-ID", b"mixed-case-name")])

    assert echoed(headers) == b"mixed-case-name"


@pytest.mark.parametrize(
    ("first", "second"),
    [
        pytest.param(b"first-valid", b"second-valid", id="both-valid"),
        pytest.param(b"first-valid", b"bad id!", id="valid-then-malformed"),
        pytest.param(b"bad id!", b"second-valid", id="malformed-then-valid"),
    ],
)
async def test_two_incoming_request_ids_yield_one_unambiguous_id(
    app: FastAPI, first: bytes, second: bytes
) -> None:
    """A request that arrives with the header twice must not produce two IDs, and must not
    produce a joined value: the ID reaches logs and error bodies, where it has to identify
    exactly one request."""
    headers = await response_headers(app, [(b"x-request-id", first), (b"x-request-id", second)])

    returned = echoed(headers)
    assert b"," not in returned, f"the two headers were joined: {returned!r}"
    assert ALLOWED_BYTES.fullmatch(returned), returned
    assert returned in {first, second} or GENERATED.fullmatch(returned.decode("ascii")), returned


async def test_a_handler_cannot_forge_the_echoed_request_id(settings: Settings) -> None:
    """A route (or a later slice's middleware) that sets its own X-Request-ID must not be able
    to make the response disagree with the logs."""

    async def forge() -> JSONResponse:
        return JSONResponse({"ok": True}, headers={"X-Request-ID": "forged-by-the-handler"})

    application = create_app(settings)
    application.add_api_route("/__heldout__/forge", forge, methods=["GET"])

    headers = await response_headers(
        application, [(b"x-request-id", b"authoritative")], path="/__heldout__/forge"
    )

    assert echoed(headers) == b"authoritative"


async def test_the_request_id_does_not_leak_out_of_the_request(app: FastAPI) -> None:
    """The context variable is reset when the request ends, so a later request -- or a
    background task in a later slice -- can never log another request's ID."""
    assert current_request_id() is None

    await response_headers(app, [(b"x-request-id", b"inside-the-request")])

    assert current_request_id() is None


ECHO_PATHS = [
    pytest.param("GET", HEALTH, {}, id="200-ok"),
    pytest.param("HEAD", HEALTH, {}, id="head"),
    pytest.param("POST", HEALTH, {}, id="405"),
    pytest.param("GET", "/api/no-such/route", {}, id="404"),
    pytest.param("GET", "/api/health/live/", {}, id="307-trailing-slash"),
    pytest.param(
        "OPTIONS",
        HEALTH,
        {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        id="cors-preflight-allowed",
    ),
    pytest.param(
        "OPTIONS",
        HEALTH,
        {"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
        id="cors-preflight-refused",
    ),
    pytest.param(
        "OPTIONS",
        HEALTH,
        {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Not-Allowed",
        },
        id="cors-preflight-refused-headers",
    ),
]


@pytest.mark.parametrize(("method", "path", "extra"), ECHO_PATHS)
async def test_the_request_id_is_echoed_on_every_reachable_response(
    client: httpx.AsyncClient, method: str, path: str, extra: dict[str, str]
) -> None:
    """ "Always echoed" has to hold on the paths that never reach a route handler too --
    including the responses CORS middleware writes by itself."""
    sent = f"sweep-{uuid.uuid4().hex[:12]}"

    response = await client.request(
        method, path, headers={"X-Request-ID": sent, **extra}, follow_redirects=False
    )

    returned = [v for k, v in response.headers.multi_items() if k.lower() == "x-request-id"]
    assert returned == [sent], f"{method} {path} -> {response.status_code}: {returned}"


async def test_concurrent_requests_mixing_valid_and_malformed_ids_do_not_cross(
    client: httpx.AsyncClient,
) -> None:
    """Twenty overlapping requests: every valid ID comes back to its own caller, every
    malformed one is replaced, and no generated ID is handed to two callers."""
    valid = [f"mixed-{i:02d}-{uuid.uuid4().hex[:8]}" for i in range(10)]
    malformed = [f"bad id {i}!" for i in range(10)]
    sent = [value for pair in zip(valid, malformed, strict=True) for value in pair]

    responses = await asyncio.gather(
        *(client.get(SLOW_ROUTE, headers={"X-Request-ID": value}) for value in sent)
    )
    returned = [response.headers["x-request-id"] for response in responses]

    for value, got in zip(sent, returned, strict=True):
        if value in valid:
            assert got == value
        else:
            assert got != value and GENERATED.fullmatch(got), got
    assert len(set(returned)) == len(returned), f"an ID was reused: {returned}"
