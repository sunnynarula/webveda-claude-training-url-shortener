"""Held-out tests for the test-database guard (TASKS.md slice 1, acceptance 8).

The guard exists so a destructive fixture -- `DROP SCHEMA`, `TRUNCATE` -- can only ever run
against a local `*_test` database. It gets one string and has to decide from that alone, so
what matters is not how it reads a well-formed URL but whether a URL that *reads* as local can
still send a client somewhere else.

`urlsplit` is only one of several parsers such a string meets. asyncpg parses it with
`urllib.parse`; psql, psycopg and `pg_dump` parse it with libpq, which has no notion of a
fragment and treats `?` as the start of the parameter list wherever it appears. Where two
parsers disagree, the guard has to side with the more permissive one.
"""

import pytest

from testsupport.db_guard import UnsafeTestDatabaseError, ensure_safe_test_database_url

LOCAL = "postgresql://u:p@localhost:5432/urlshortener_test"


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(
            "postgresql://u:p@localhost/urlshortener_test#?host=db.prod.example.com",
            id="fragment-hides-a-host-override",
        ),
        pytest.param(
            "postgresql://u:p@localhost/urlshortener_test#?dbname=urlshortener",
            id="fragment-hides-a-dbname-override",
        ),
    ],
)
def test_a_fragment_cannot_hide_a_parameter(url: str) -> None:
    """`urlsplit` puts everything after `#` in the fragment, so the guard sees no query at
    all. libpq does not implement fragments: for it the parameter list starts at the `?` and
    the connection goes to the host named there."""
    with pytest.raises(UnsafeTestDatabaseError):
        ensure_safe_test_database_url(url)


@pytest.mark.parametrize(
    "key",
    [
        pytest.param("HOST", id="host-upper"),
        pytest.param("Host", id="host-title"),
        pytest.param("DBNAME", id="dbname-upper"),
        pytest.param("Service", id="service-title"),
    ],
)
def test_an_override_is_refused_whatever_its_case(key: str) -> None:
    """The guard compares parameter names case-sensitively. Neither libpq nor asyncpg accepts
    an upper-cased keyword today, so this is defence in depth rather than a live hole -- but
    it is the kind of asymmetry that stops being theoretical when a driver changes."""
    with pytest.raises(UnsafeTestDatabaseError):
        ensure_safe_test_database_url(f"{LOCAL}?{key}=db.prod.example.com")


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(
            "postgresql://localhost:5432@db.prod.example.com/urlshortener_test",
            id="safe-host-in-the-userinfo",
        ),
        pytest.param(
            "postgresql://u:localhost@db.prod.example.com/urlshortener_test",
            id="safe-host-in-the-password",
        ),
        pytest.param(
            "postgresql://u:p@localhost,db.prod.example.com:5432/urlshortener_test",
            id="libpq-multi-host-list",
        ),
        pytest.param(
            "postgresql://u:p@db.prod.example.com#@localhost/urlshortener_test",
            id="fragment-after-the-real-host",
        ),
        pytest.param("postgresql://u:p@localhost.evil.example/x_test", id="local-looking-suffix"),
        pytest.param("postgresql://u:p@127.0.0.1.evil.example/x_test", id="local-looking-ip"),
        pytest.param("postgresql://u:p@[::ffff:127.0.0.1]/x_test", id="ipv4-mapped-ipv6"),
        pytest.param("postgresql://u:p@127.0.0.2/x_test", id="other-loopback-address"),
        pytest.param("postgresql://u:p@2130706433/x_test", id="loopback-as-an-integer"),
        pytest.param("postgresql://u:p@localhost./x_test", id="fully-qualified-localhost"),
        pytest.param(f"{LOCAL}?hostaddr=203.0.113.9", id="hostaddr-override"),
        pytest.param(f"{LOCAL}?host=db.prod.example.com", id="host-override"),
        pytest.param(f"{LOCAL}?dbname=urlshortener", id="dbname-override"),
        pytest.param(f"{LOCAL}?database=urlshortener", id="database-override"),
        pytest.param(f"{LOCAL}?service=production", id="service-override"),
        pytest.param("postgresql:///urlshortener_test", id="no-host-at-all"),
        pytest.param("postgresql://u:p@localhost/urlshortener", id="no-test-suffix"),
        pytest.param("postgresql://u:p@localhost/URLSHORTENER_TEST", id="upper-case-name"),
        pytest.param("postgresql://u:p@localhost/", id="no-database-name"),
        pytest.param("postgresql://u:p@localhost", id="no-path"),
        pytest.param("", id="empty-string"),
        pytest.param("not a url", id="not-a-url"),
    ],
)
def test_the_guard_refuses_anything_that_might_not_be_the_local_test_database(url: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        ensure_safe_test_database_url(url)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param("postgresql+asyncpg://u:p@localhost/urlshortener_test", id="asyncpg-driver"),
        pytest.param("postgresql://u:p@LOCALHOST/urlshortener_test", id="upper-case-host"),
        pytest.param("postgresql://localhost/urlshortener_test", id="no-credentials"),
        pytest.param(f"{LOCAL}?application_name=pytest", id="harmless-parameter"),
        pytest.param("postgresql://u:p@postgres:5432/ci_test", id="ci-service"),
    ],
)
def test_the_guard_accepts_a_local_test_database_however_it_is_written(url: str) -> None:
    ensure_safe_test_database_url(url)  # passes by returning without raising


def test_the_refusal_never_prints_the_credentials() -> None:
    """The message goes to a failing CI log, which is public on a public repository."""
    with pytest.raises(UnsafeTestDatabaseError) as caught:
        ensure_safe_test_database_url("postgresql://admin:hunter2@db.prod.example.com/app")

    message = str(caught.value)
    assert "hunter2" not in message, message
    assert "admin" not in message, message
