"""Refuse to run destructive test fixtures against anything but a local `*_test` database."""

from urllib.parse import parse_qs, unquote, urlsplit

_SAFE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres"})
# libpq and asyncpg let the query string override the host or database in the URL.
_OVERRIDES = frozenset({"host", "hostaddr", "dbname", "database", "service"})


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when TEST_DATABASE_URL could point at real data."""


def ensure_safe_test_database_url(url: str) -> None:
    """Raise UnsafeTestDatabaseError unless the database name ends in `_test` and the
    host is `localhost`, `127.0.0.1`, `::1` or `postgres` (the CI service)."""
    parts = urlsplit(url)
    overrides = _OVERRIDES & parse_qs(parts.query).keys()
    if overrides:
        raise UnsafeTestDatabaseError(
            f"test database URL overrides {sorted(overrides)} in its query"
        )
    if parts.hostname not in _SAFE_HOSTS:
        raise UnsafeTestDatabaseError(
            f"test database host {parts.hostname!r} is not one of {sorted(_SAFE_HOSTS)}"
        )
    name = unquote(parts.path.lstrip("/"))
    if not name.endswith("_test"):
        raise UnsafeTestDatabaseError(f"test database name {name!r} does not end in _test")
