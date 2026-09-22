"""Refuse to run destructive test fixtures against anything but a local `*_test` database."""


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when TEST_DATABASE_URL could point at real data."""


def ensure_safe_test_database_url(url: str) -> None:
    """Raise UnsafeTestDatabaseError unless the database name ends in `_test` and the
    host is `localhost`, `127.0.0.1`, `::1` or `postgres` (the CI service)."""
    raise NotImplementedError
