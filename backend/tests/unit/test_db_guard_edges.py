"""Test-database guard edge cases beyond the slice 1 contract."""

import pytest

from testsupport.db_guard import UnsafeTestDatabaseError, ensure_safe_test_database_url


@pytest.mark.parametrize(
    "url",
    [
        # libpq and asyncpg let the query string replace the host or database
        "postgresql://u:p@localhost/urlshortener_test?host=db.example.com",
        "postgresql://u:p@localhost/urlshortener_test?hostaddr=10.0.0.5",
        "postgresql://u:p@localhost/urlshortener_test?dbname=urlshortener",
        "postgresql://u:p@localhost/urlshortener_test?service=prod",
        # several hosts, one of them remote
        "postgresql://u:p@localhost,db.example.com/urlshortener_test",
        # a Unix socket: no host in the URL at all
        "postgresql:///urlshortener_test",
    ],
)
def test_ways_round_the_host_or_name_check_are_refused(url: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        ensure_safe_test_database_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@[::1]:5432/urlshortener_test",
        "postgresql+asyncpg://u:p@postgres/urlshortener_test",
        "postgresql://u:p@127.0.0.1/urlshortener%5Ftest",  # percent-encoded underscore
    ],
)
def test_local_test_databases_are_accepted(url: str) -> None:
    ensure_safe_test_database_url(url)
