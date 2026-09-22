"""JsonFormatter and configure_logging details."""

import json
import logging
import sys

from app.logging_config import JsonFormatter, configure_logging
from app.request_context import request_id_var


def record(**extra: object) -> logging.LogRecord:
    rec = logging.makeLogRecord(
        {"name": "app.test", "levelname": "INFO", "msg": "hi %s", "args": ("x",)}
    )
    for key, value in extra.items():
        setattr(rec, key, value)
    return rec


def test_extras_and_request_id_are_included() -> None:
    token = request_id_var.set("rid-1")
    try:
        line = JsonFormatter().format(record(route="/r", status=200))
    finally:
        request_id_var.reset(token)
    entry = json.loads(line)
    assert entry["message"] == "hi x"
    assert entry["request_id"] == "rid-1"
    assert entry["route"] == "/r"
    assert entry["status"] == 200


def test_uvicorn_colour_duplicate_is_dropped() -> None:
    entry = json.loads(JsonFormatter().format(record(color_message="\x1b[1mhi\x1b[0m")))
    assert "color_message" not in entry


def test_exception_text_is_included() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        rec = record()
        rec.exc_info = sys.exc_info()
    entry = json.loads(JsonFormatter().format(rec))
    assert "ValueError: boom" in entry["exception"]


def test_configure_logging_sets_the_level() -> None:
    configure_logging("warning")
    assert logging.getLogger("app").level == logging.WARNING
    assert logging.getLogger("uvicorn").level == logging.WARNING
    configure_logging("INFO")
    assert logging.getLogger("app").level == logging.INFO
