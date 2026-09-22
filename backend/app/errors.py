"""RFC 9457 problem responses (ADR 0002)."""

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.request_context import current_request_id

PROBLEM_JSON = "application/problem+json"

_CODES_BY_STATUS = {
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    429: "rate_limited",
}


def problem_response(
    status: int,
    code: str,
    detail: str,
    *,
    extra: dict[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """An `application/problem+json` response carrying our `code` and the request ID."""
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status).phrase,
        "status": status,
        "detail": detail,
        "code": code,
        "request_id": current_request_id(),
    }
    if extra:
        body.update(extra)
    return JSONResponse(body, status_code=status, media_type=PROBLEM_JSON, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    """Route framework errors through problem_response. Unhandled exceptions become
    problems in middleware.CatchAllMiddleware instead, so outer middleware still runs."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        code = _CODES_BY_STATUS.get(exc.status_code, "http_error")
        return problem_response(exc.status_code, code, detail, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Where and why only: never the submitted value (`input`) or its context (`ctx`).
        errors = [
            {
                "loc": list(err.get("loc", ())),
                "msg": err.get("msg", ""),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]
        return problem_response(
            422, "invalid_request", "The request is malformed.", extra={"errors": errors}
        )
