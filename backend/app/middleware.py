"""Request ID, access log and catch-all 500 middleware (ADR 0002, CLAUDE.md §9).

Pure ASGI rather than BaseHTTPMiddleware, so streaming responses and background
tasks keep working.
"""

import logging
import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import problem_response
from app.request_context import request_id_var

_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")

access_log = logging.getLogger("app.access")
error_log = logging.getLogger("app.error")


def _header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get("headers", []):
        if key.lower() == name:
            return str(value.decode("latin-1"))
    return None


class RequestIdMiddleware:
    """Outermost. Accept a well-formed incoming X-Request-ID or generate one, echo it,
    expose it to logs and errors, and write one access-log line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, b"x-request-id")
        valid = incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming)
        request_id = incoming if valid and incoming else uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = 500

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
            route = scope.get("route")
            access_log.info(
                "request",
                extra={
                    "event": "request",
                    "method": scope["method"],
                    "route": getattr(route, "path", None) or "(unmatched)",
                    "status": status,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id_var.reset(token)


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
                raise
            response = problem_response(
                500, "internal_error", "The server hit an unexpected error."
            )
            await response(scope, receive, send)
