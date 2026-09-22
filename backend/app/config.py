"""Settings, read from environment variables (CLAUDE.md §10).

In development a `.env` file in `backend/` is read too. Tests must never read
it: construct `Settings(_env_file=None, ...)` with explicit values.
"""

from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


def bare_origin(value: str) -> str:
    """Accept a bare origin (scheme, host, optional port) and return it without a
    trailing slash. https is required, except for local hosts."""
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("must be an http(s) origin such as https://example.com")
    if parts.path not in {"", "/"} or parts.query or parts.fragment or parts.username:
        raise ValueError("must be a bare origin: no path, query, fragment or credentials")
    if parts.scheme == "http" and parts.hostname not in _LOCAL_HOSTS:
        raise ValueError("must use https (plain http is allowed only for localhost)")
    _ = parts.port  # raises ValueError for a malformed or out-of-range port
    return value.rstrip("/")


class Settings(BaseSettings):
    """Runtime configuration (CLAUDE.md §10)."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    redis_url: str
    public_base_url: str
    frontend_origin: str
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)

    @field_validator("public_base_url", "frontend_origin")
    @classmethod
    def _must_be_bare_origin(cls, value: str) -> str:
        return bare_origin(value)

    @field_validator("log_level")
    @classmethod
    def _must_be_log_level(cls, value: str) -> str:
        level = value.upper()
        if level not in _LOG_LEVELS:
            raise ValueError(f"must be one of {', '.join(_LOG_LEVELS)}")
        return level
