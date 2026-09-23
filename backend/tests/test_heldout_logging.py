"""Held-out tests for JSON logging (TASKS.md slice 1, acceptance 7; CLAUDE.md §9).

Acceptance test 7 runs the real server and checks that every line is JSON, that one access
line names the route, and that the query string never appears. These tests take the same
claims apart in-process, where a failure names the line that broke, and push on the parts a
single smoke request cannot reach: a multi-line traceback, a second `create_app` doubling the
handlers, the path as opposed to the query string, an ID that was rejected, and overlapping
requests each keeping their own ID.

The logging config writes to `ext://sys.stdout`, resolved when `create_app` calls
`dictConfig`. Replacing `sys.stdout` before that call is therefore enough to capture it.
"""

import asyncio
import contextlib
import io
import json
import logging
import sys
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from app.config import Settings
from app.logging_config import configure_logging
from app.main import create_app

HEALTH = "/api/health/live"
SLOW_ROUTE = "/__heldout__/slow"
RAISE_ROUTE = "/__heldout__/raise"
ACCESS_FIELDS = {"request_id", "method", "route", "status", "duration_ms"}
MULTILINE_MESSAGE = 'probe failure\nsecond line "quoted"\tand tabbed'


async def slow() -> dict[str, str]:
    await asyncio.sleep(0.05)
    return {"status": "ok"}


async def always_raise() -> None:
    raise RuntimeError(MULTILINE_MESSAGE)


@contextlib.contextmanager
def capturing_logs(level: str = "INFO") -> Iterator[io.StringIO]:
    """Capture everything the logging handlers write, then put logging back.

    This is a context manager rather than a fixture on purpose: pytest re-installs its own
    ``sys.stdout`` when it resumes capturing for the call phase, so a replacement made during
    fixture setup would be undone before the test body runs. The app has to be built inside
    the block, because that is when ``dictConfig`` resolves ``ext://sys.stdout``.
    """
    buffer = io.StringIO()
    original = sys.stdout
    sys.stdout = buffer
    try:
        # Binds the handlers to the captured stream. This used to happen as a side
        # effect of create_app; issue #18 made configuring logging the caller's job.
        configure_logging(level)
        yield buffer
    finally:
        sys.stdout = original
        configure_logging("INFO")


def build(settings: Settings) -> FastAPI:
    """An app with the two probe routes. Built inside the capture block so its handlers are
    bound to the captured stream."""
    application = create_app(settings)
    application.add_api_route(SLOW_ROUTE, slow, methods=["GET"])
    application.add_api_route(RAISE_ROUTE, always_raise, methods=["GET"])
    return application


def client_for(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def lines(buffer: io.StringIO) -> list[str]:
    return [line for line in buffer.getvalue().splitlines() if line.strip()]


def records(buffer: io.StringIO) -> list[dict[str, Any]]:
    """Every captured line, parsed. A line that is not a JSON object fails the test here,
    because a log shipper would drop it."""
    parsed: list[dict[str, Any]] = []
    for line in lines(buffer):
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            pytest.fail(f"not a JSON line ({exc}): {line!r}")
        assert isinstance(value, dict), f"not a JSON object: {line!r}"
        parsed.append(value)
    return parsed


def access_lines(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [record for record in records(buffer) if record.get("event") == "request"]


async def test_building_the_app_twice_does_not_double_the_log_lines(settings: Settings) -> None:
    """`configure_logging` calls `dictConfig`. If that appended handlers instead of
    replacing them, every line would be written once per call -- and a process that
    configures logging twice, as a reload or a test fixture does, would double it."""
    with capturing_logs() as log_stream:
        configure_logging("INFO")
        app = build(settings)

        async with client_for(app) as client:
            await client.get(HEALTH, headers={"X-Request-ID": "double-build"})

    written = [
        record for record in access_lines(log_stream) if record["request_id"] == "double-build"
    ]
    assert len(written) == 1, f"{len(written)} access lines for one request: {written}"


async def test_a_traceback_stays_on_one_line(settings: Settings) -> None:
    """A multi-line exception is the classic way a JSON log stops being one object per line."""
    with capturing_logs() as log_stream:
        app = build(settings)

        async with client_for(app) as client:
            response = await client.get(RAISE_ROUTE)

    assert response.status_code == 500
    parsed = records(log_stream)  # fails on the first line that is not a JSON object
    with_traceback = [record for record in parsed if "exception" in record]
    assert with_traceback, f"the 500 logged no traceback: {parsed}"
    assert any("RuntimeError" in str(record["exception"]) for record in with_traceback)


async def test_no_log_line_repeats_the_path_the_query_or_a_rejected_request_id(
    settings: Settings,
) -> None:
    """The access line records the route template. Slice 4 puts the short code in the path and
    slice 3 puts the submitted URL in the body, so "never the real path" is what keeps the
    logs free of user data -- and a rejected request ID must not be written anywhere either,
    or a client could choose what a log line says."""
    path_marker = f"path{uuid.uuid4().hex}"
    query_marker = f"query{uuid.uuid4().hex}"
    rejected = 'rid" ,"level":"CRITICAL'

    with capturing_logs() as log_stream:
        app = build(settings)

        async with client_for(app) as client:
            response = await client.get(
                f"/api/{path_marker}",
                params={"leak": query_marker},
                headers={"X-Request-ID": rejected},
            )

    assert response.status_code == 404
    text = "\n".join(lines(log_stream))
    assert path_marker not in text, text
    assert query_marker not in text, text
    assert "leak" not in text, text
    assert "CRITICAL" not in text, text
    assert [record["route"] for record in access_lines(log_stream)] == ["(unmatched)"]


@pytest.mark.parametrize(
    ("path", "method", "status"),
    [
        pytest.param(HEALTH, "GET", 200, id="ok"),
        pytest.param("/api/nope", "GET", 404, id="not-found"),
        pytest.param(HEALTH, "POST", 405, id="method-not-allowed"),
        pytest.param(RAISE_ROUTE, "GET", 500, id="internal-error"),
    ],
)
async def test_one_access_line_records_the_outcome_of_every_kind_of_request(
    settings: Settings, path: str, method: str, status: int
) -> None:
    """A request that fails is the one you most need in the log."""
    sent = f"outcome-{uuid.uuid4().hex[:8]}"

    with capturing_logs() as log_stream:
        app = build(settings)

        async with client_for(app) as client:
            response = await client.request(method, path, headers={"X-Request-ID": sent})

    assert response.status_code == status
    written = [record for record in access_lines(log_stream) if record["request_id"] == sent]
    assert len(written) == 1, written
    entry = written[0]
    assert ACCESS_FIELDS <= entry.keys(), f"lacks {sorted(ACCESS_FIELDS - entry.keys())}"
    assert entry["status"] == status
    assert entry["method"] == method
    assert isinstance(entry["duration_ms"], int | float) and not isinstance(
        entry["duration_ms"], bool
    )


async def test_overlapping_requests_do_not_share_a_request_id_in_the_logs(
    settings: Settings,
) -> None:
    """The ID lives in a context variable. If it leaked between tasks, the access lines would
    still look plausible -- they would just blame the wrong request."""
    sent = [f"concurrent-{i:02d}-{uuid.uuid4().hex[:8]}" for i in range(10)]

    with capturing_logs() as log_stream:
        app = build(settings)

        async with client_for(app) as client:
            await asyncio.gather(
                *(client.get(SLOW_ROUTE, headers={"X-Request-ID": value}) for value in sent)
            )

    logged = [record["request_id"] for record in access_lines(log_stream)]
    assert sorted(logged) == sorted(sent), logged
    for record in access_lines(log_stream):
        assert record["route"] == SLOW_ROUTE
        assert record["status"] == 200


def test_uvicorns_access_logger_is_silenced_and_its_error_logger_is_json(
    settings: Settings,
) -> None:
    """uvicorn's own access line carries the query string, so it is turned off and ours
    replaces it. Its error logger has to keep working, in JSON."""
    with capturing_logs() as log_stream:
        create_app(settings)

        logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /x?leak=1 HTTP/1.1" 200')
        logging.getLogger("uvicorn.error").info("Application startup complete.")

    parsed = records(log_stream)
    assert not any("leak=1" in json.dumps(record) for record in parsed), parsed
    assert [record["message"] for record in parsed] == ["Application startup complete."]
    assert parsed[0]["logger"] == "uvicorn.error"
    assert parsed[0]["request_id"] is None


async def test_the_log_level_setting_reaches_the_app_and_uvicorn_loggers(
    make_settings: Callable[..., Settings],
) -> None:
    """At WARNING the access line goes away -- worth knowing, since `LOG_LEVEL=WARNING` looks
    like a way to quieten a noisy deployment rather than a way to lose its audit trail."""
    settings = make_settings(log_level="WARNING")

    with capturing_logs(settings.log_level) as log_stream:
        app = build(settings)

        async with client_for(app) as client:
            await client.get(HEALTH, headers={"X-Request-ID": "quiet"})
            await client.get(RAISE_ROUTE)

    assert access_lines(log_stream) == []
    assert any(record.get("level") == "ERROR" for record in records(log_stream))
