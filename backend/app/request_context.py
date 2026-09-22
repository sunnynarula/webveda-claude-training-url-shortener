"""The current request's ID, readable anywhere in that request's task (logs, errors)."""

from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def current_request_id() -> str | None:
    """The ID of the request being handled, or None outside a request."""
    return request_id_var.get()
