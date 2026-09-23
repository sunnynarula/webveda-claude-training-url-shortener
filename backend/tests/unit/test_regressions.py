"""One test per fixed issue, named after it.

The held-out tests in `backend/tests/` cover these behaviours too, but they are grouped
by subject and say nothing about which defect they guard. This file is the regression
marker named when an issue is closed: revert a fix and the test that fails tells you
which issue came back. Each test is the smallest reproduction of the original report.
"""

import ssl

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pydantic import ValidationError

from app.config import Settings, bare_origin
from app.database import asyncpg_url_and_args
from app.main import create_app
from testsupport.db_guard import UnsafeTestDatabaseError, ensure_safe_test_database_url

LOCAL_TEST_DB = "postgresql://u:p@localhost/urlshortener_test"
NEON = "postgresql://user:pw@ep-x-pooler.eu-central-1.aws.neon.tech/neondb"


def test_issue_1_an_origin_never_keeps_an_invisible_character() -> None:
    """A trailing newline parsed clean and was stored, because the value returned was
    the caller's string rather than the one that had been validated."""
    with pytest.raises(ValueError, match="control characters"):
        bare_origin("https://sho.rt\n")
    assert "\t" not in bare_origin("https://sho.rt")


async def test_issue_2_a_capitalised_frontend_origin_still_matches_the_browser() -> None:
    """FRONTEND_ORIGIN=http://LOCALHOST:5173 was accepted and then never matched an
    Origin header, so the frontend was blocked by CORS with nothing to explain it."""
    settings = Settings(
        _env_file=None,
        database_url="postgresql://u:p@localhost/db",
        redis_url="redis://localhost:6379/0",
        public_base_url="https://sho.rt",
        frontend_origin="http://LOCALHOST:5173",
    )
    assert settings.frontend_origin == "http://localhost:5173"

    async with LifespanManager(create_app(settings)) as manager:
        transport = httpx.ASGITransport(app=manager.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/health/live", headers={"Origin": "http://localhost:5173"}
            )

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_issue_3_an_empty_sslmode_is_refused_rather_than_ignored() -> None:
    """`?sslmode=` disappeared inside SQLAlchemy's parser, so a URL that asked for TLS
    connected without it."""
    with pytest.raises(ValueError, match="sslmode"):
        asyncpg_url_and_args(f"{NEON}?sslmode=")


def test_issue_4_port_zero_is_refused() -> None:
    with pytest.raises(ValueError, match="port 0"):
        bare_origin("https://sho.rt:0")


def test_issue_5_a_required_setting_that_is_present_but_empty_is_refused() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(
            _env_file=None,
            database_url="",
            redis_url="redis://localhost:6379/0",
            public_base_url="https://sho.rt",
            frontend_origin="https://app.sho.rt",
        )


def test_issue_6_a_fragment_cannot_hide_a_parameter_from_the_guard() -> None:
    """psql connects to `postgres` for this URL: libpq has no fragments, so the guard's
    urlsplit view and the client's view disagreed."""
    with pytest.raises(UnsafeTestDatabaseError, match="#"):
        ensure_safe_test_database_url(f"{LOCAL_TEST_DB}#?dbname=postgres")


@pytest.mark.parametrize("parameter", ["host", "HOST", "Host", "dbname", "DBNAME"])
def test_issue_7_an_override_is_refused_whatever_its_case(parameter: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError, match="could change what it reaches"):
        ensure_safe_test_database_url(f"{LOCAL_TEST_DB}?{parameter}=db.prod.example.com")


async def test_issue_8_head_is_answered_with_the_headers_and_no_body(
    client: httpx.AsyncClient,
) -> None:
    """HEAD returned 405, although GET on the same address returned 200."""
    head = await client.head("/api/health/live")
    get = await client.get("/api/health/live")

    assert head.status_code == 200
    assert head.content == b""
    assert head.headers.get("content-type") == get.headers.get("content-type")
    assert head.headers.get("x-request-id")


async def test_issue_10_a_trailing_slash_is_not_redirected(client: httpx.AsyncClient) -> None:
    """The redirect was built from the client's own Host header and carried the query
    string back in a response header."""
    response = await client.get(
        "/api/health/live/?leak=secret", headers={"Host": "attacker.example"}
    )

    assert response.status_code == 404
    assert "location" not in response.headers
    assert "secret" not in response.text


def test_issue_11_a_parameter_asyncpg_cannot_take_is_refused_at_startup() -> None:
    """These built an engine happily and raised TypeError on the first connection."""
    with pytest.raises(ValueError, match="unsupported database URL parameter"):
        asyncpg_url_and_args(f"{NEON}?sslmode=require&made_up=1")

    _, connect_args = asyncpg_url_and_args(f"{NEON}?sslmode=require&application_name=x")
    assert connect_args["server_settings"] == {"application_name": "x"}


def test_issue_12_plain_http_is_allowed_on_the_ipv6_loopback() -> None:
    """Decided in #12: ::1 is the same machine, so the contract's wording changed."""
    assert bare_origin("http://[::1]:5173") == "http://[::1]:5173"


def test_issue_17_the_database_url_hides_its_password_when_printed() -> None:
    """It was returned as a plain string, so the password was one log line away from a
    log aggregator. A URL object masks it in every str(), repr() and traceback."""
    url, _ = asyncpg_url_and_args("postgresql://app_user:SuperSecret123@db.example.com/app")

    assert "SuperSecret123" not in str(url)
    assert "SuperSecret123" not in repr(url)
    assert "SuperSecret123" not in f"connecting to {url}"
    # Still available where it is genuinely needed, by asking for it in the open.
    assert url.render_as_string(hide_password=False).count("SuperSecret123") == 1


@pytest.mark.parametrize("mode", ["require", "verify-ca", "verify-full"])
def test_issue_15_a_mode_that_requires_tls_verifies_the_certificate(mode: str) -> None:
    """asyncpg cannot do channel binding, so verifying the certificate is the only
    protection left against an intercepted database connection."""
    _, connect_args = asyncpg_url_and_args(f"{NEON}?sslmode={mode}&channel_binding=require")

    context = connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname
