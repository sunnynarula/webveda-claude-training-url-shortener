"""Acceptance test 8 (TASKS.md, slice 1; docs/PLAN.md §5): destructive test fixtures only ever
touch a local ``*_test`` database."""

import pytest

from testsupport.db_guard import UnsafeTestDatabaseError, ensure_safe_test_database_url


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("postgresql://u:p@localhost:5432/urlshortener", id="no-test-suffix"),
        pytest.param("postgresql://u:p@db.example.com:5432/urlshortener_test", id="remote-host"),
        pytest.param(
            "postgresql://u:p@localhost.example.com:5432/urlshortener_test",
            id="lookalike-local-host",
        ),
        pytest.param(
            "postgresql://u:p@localhost:5432/urlshortener_test_copy", id="test-not-at-the-end"
        ),
    ],
)
def test_guard_refuses_unsafe_database(url: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        ensure_safe_test_database_url(url)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("postgresql://u:p@localhost/urlshortener_test", id="localhost"),
        pytest.param("postgresql://u:p@127.0.0.1:5432/urlshortener_test", id="ipv4-loopback"),
        pytest.param("postgresql://u:p@[::1]:5432/urlshortener_test", id="ipv6-loopback"),
        pytest.param("postgresql://u:p@postgres:5432/urlshortener_test", id="ci-service"),
    ],
)
def test_guard_accepts_local_test_database(url: str) -> None:
    ensure_safe_test_database_url(url)  # passes by returning without raising
