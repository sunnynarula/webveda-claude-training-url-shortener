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
    """Rebuild a bare origin (scheme, host, optional port) from the parts that were
    checked. https is required, except for the local hosts.

    The value returned is built from those parts rather than echoed back (ADR 0012).
    `urlsplit` deletes tabs and newlines anywhere in a URL and trims leading
    whitespace before parsing, and lower-cases the host only in its own view of it,
    so returning the caller's string would store something we never validated.
    """
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise ValueError("must not contain spaces or control characters")
    parts = urlsplit(value)
    host = parts.hostname  # lower-cased, and without the brackets of an IPv6 literal
    if parts.scheme not in {"http", "https"} or not host:
        raise ValueError("must be an http(s) origin such as https://example.com")
    if parts.path not in {"", "/"} or parts.query or parts.fragment:
        raise ValueError("must be a bare origin: no path, query or fragment")
    if parts.username or parts.password:
        raise ValueError("must not carry credentials")
    if parts.scheme == "http" and host not in _LOCAL_HOSTS:
        raise ValueError("must use https (plain http is allowed only for the local hosts)")
    port = parts.port  # raises ValueError for a malformed or out-of-range port
    if port == 0:
        raise ValueError("port 0 means 'any free port' and cannot be reached")
    authority = f"[{host}]" if ":" in host else host  # put an IPv6 literal back in brackets
    return f"{parts.scheme}://{authority}" + (f":{port}" if port is not None else "")


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

    @field_validator("database_url", "redis_url")
    @classmethod
    def _must_not_be_blank(cls, value: str) -> str:
        """`DATABASE_URL=` in a deployment is a variable somebody forgot to fill in.
        Caught here it names itself; caught on first use it is a connection error
        during someone's request. What each URL must *contain* is checked in slice 2,
        where the app first connects."""
        if not value.strip():
            raise ValueError("must not be empty")
        if value != value.strip():
            raise ValueError("must not be padded with whitespace")
        return value

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
