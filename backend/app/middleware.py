"""Request ID, access log and catch-all 500 middleware (ADR 0002, CLAUDE.md §9).

Both are pure ASGI rather than BaseHTTPMiddleware, because both work at the level of
ASGI messages: one replaces a header on `http.response.start` and logs once the response
has gone out, the other has to know whether a response had already started before it can
replace it with a 500.
"""

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import problem_response
from app.request_context import request_id_var

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")
# The status recorded when the app never started a response: it raised instead.
_NO_RESPONSE = 500

access_log = logging.getLogger("app.access")
error_log = logging.getLogger("app.error")


def _header(scope: Scope, name: bytes) -> str | None:
    """The first value of a request header, or None. ASGI headers are raw bytes, and a
    scope is typed as Any, so the decoded value is narrowed back to str."""
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return str(value.decode("latin-1"))
    return None


def _resolve_request_id(incoming: str | None) -> str:
    """Keep a well-formed incoming ID, or make one up. The ID reaches logs and error
    bodies, so an arbitrary client-supplied string is not carried into either."""
    if incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return uuid.uuid4().hex


def _route_template(scope: Scope) -> str:
    """The matched route's template, such as `/api/health/live`. Never the real path,
    which in later slices carries the short code, and never the query string."""
    route = scope.get("route")
    return str(getattr(route, "path", None) or "(unmatched)")


class RequestIdMiddleware:
    """Outermost. Accept a well-formed incoming X-Request-ID or generate one, echo it,
    expose it to logs and errors, and write one access-log line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = _resolve_request_id(_header(scope, b"x-request-id"))
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = _NO_RESPONSE

        async def send_with_id(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                headers = [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            access_log.info(
                "request",
                extra={
                    "event": "request",
                    "method": scope["method"],
                    "route": _route_template(scope),
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id_var.reset(token)


class HeadAsGetMiddleware:
    """Answer HEAD as GET, with the same headers and no body (RFC 9110 §9.3.2).

    Not done by naming both methods on each route: FastAPI then generates two OpenAPI
    operations sharing one operation id, which breaks the client types generated from
    the schema. Here it costs one operation per route and covers every GET route,
    including the redirect in slice 4, which must answer HEAD without counting a click.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "HEAD":
            await self.app(scope, receive, send)
            return

        body_sent = False

        async def send_without_body(message: Message) -> None:
            nonlocal body_sent
            if message["type"] == "http.response.body":
                if body_sent:  # a streaming response: the rest of its chunks are dropped
                    return
                body_sent = True
                message = {**message, "body": b"", "more_body": False}
            await send(message)

        # The same scope, swapped and swapped back — not a copy. The router records the
        # route it matched on the scope it was handed, so a copy would keep the route
        # template from the access log, and every HEAD would read as "(unmatched)".
        scope["method"] = "GET"
        # A route that must behave differently for HEAD reads request.state.head_request:
        # slice 4's redirect answers HEAD without counting a click (CLAUDE.md §6).
        scope.setdefault("state", {})["head_request"] = True
        try:
            await self.app(scope, receive, send_without_body)
        finally:
            scope["method"] = "HEAD"  # so the access line says what was asked for


class CatchAllMiddleware:
    """Innermost. Turn any unhandled exception into the JSON 500 of ADR 0002, so the
    request-ID and CORS middleware outside it still add their headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            error_log.exception("unhandled error")
            if response_started:
                # The status and headers have already gone out; only the server can
                # decide what to do with a half-sent response.
                raise
            response = problem_response(
                500, "internal_error", "The server hit an unexpected error."
            )
            await response(scope, receive, send)
