"""JSON logging for the app and for uvicorn's own loggers (CLAUDE.md §9)."""

from typing import Any

LOGGING_CONFIG: dict[str, Any] = {}


def configure_logging(level: str) -> None:
    """Apply LOGGING_CONFIG at the given level."""
    raise NotImplementedError
