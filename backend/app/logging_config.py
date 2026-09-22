"""JSON logging for the app and for uvicorn's own loggers (CLAUDE.md §9)."""

import copy
import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

from app.request_context import current_request_id

# Every LogRecord has these attributes. Anything else on a record came from `extra=`.
# `color_message` is uvicorn's ANSI-coloured duplicate of the message.
_RECORD_ATTRS = frozenset(vars(logging.makeLogRecord({}))) | {"message", "color_message"}


class JsonFormatter(logging.Formatter):
    """One JSON object per line, carrying the ID of the request being handled."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": current_request_id(),
        }
        for key, value in vars(record).items():
            if key not in _RECORD_ATTRS and key not in entry:
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": JsonFormatter}},
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"level": "INFO"},
        # uvicorn's access line includes the query string. Ours (app.access) doesn't.
        "uvicorn.access": {"handlers": [], "level": "CRITICAL", "propagate": False},
        "app": {"handlers": ["stdout"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["stdout"], "level": "WARNING"},
}


def configure_logging(level: str) -> None:
    """Apply LOGGING_CONFIG, with the app's and uvicorn's loggers at the given level."""
    config = copy.deepcopy(LOGGING_CONFIG)
    for name in ("uvicorn", "uvicorn.error", "app"):
        config["loggers"][name]["level"] = level.upper()
    logging.config.dictConfig(config)
