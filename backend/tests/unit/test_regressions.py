"""One test per fixed issue, named after it.

The held-out tests in `backend/tests/` cover these behaviours too, but they are grouped
by subject and say nothing about which defect they guard. This file is the regression
marker named when an issue is closed: revert a fix and the test that fails tells you
which issue came back. Each test is the smallest reproduction of the original report.
"""

import contextlib
import io
import json
import logging
import ssl
import sys
from collections.abc import Iterator

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import Request
from pydantic import ValidationError

from app.config import Settings, bare_origin
from app.database import asyncpg_url_and_args
from app.logging_config import configure_logging
from app.main import create_app
from testsupport.db_guard import UnsafeTestDatabaseError, ensure_safe_test_database_url

LOCAL_TEST_DB = "postgresql://u:p@localhost/urlshortener_test"
NEON = "postgresql://user:pw@ep-x-pooler.eu-central-1.aws.neon.tech/neondb"


def test_issue_1_an_origin_never_keeps_an_invisible_character() -> None:
    """A trailing newline parsed clean and was stored, because the value returned was
    the caller's string rather than the one that had been validated."""
    with pytest.raises(ValueError, match="printable ASCII"):
        bare_origin("https://sho.rt\n")
    assert bare_origin("https://sho.rt") == "https://sho.rt", "a clean origin still passes"


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


def test_issue_18_building_the_app_leaves_the_processs_logging_alone() -> None:
    """create_app called dictConfig, which replaces the handlers of every logger in the
    process - including those of whoever imported us. Configuring logging belongs to
    whoever owns the process, which for us is `python -m app`."""
    root = logging.getLogger()
    marker = logging.NullHandler()
    original = root.handlers[:]
    root.handlers = [marker]
    try:
        create_app(
            Settings(
                _env_file=None,
                database_url="postgresql://u:p@localhost/db",
                redis_url="redis://localhost:6379/0",
                public_base_url="https://sho.rt",
                frontend_origin="https://app.sho.rt",
                log_level="WARNING",
            )
        )
        assert root.handlers == [marker], "create_app replaced the caller's log handlers"
    finally:
        root.handlers = original


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": "postgresql://u:p@localhost/db",
        "redis_url": "redis://localhost:6379/0",
        "public_base_url": "https://sho.rt",
        "frontend_origin": "https://app.sho.rt",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@contextlib.contextmanager
def capturing_logs() -> Iterator[io.StringIO]:
    """Bind the log handlers to a buffer we can read. configure_logging resolves
    `ext://sys.stdout` when it runs, so the swap has to happen first."""
    buffer = io.StringIO()
    original = sys.stdout
    sys.stdout = buffer
    try:
        configure_logging("INFO")
        yield buffer
    finally:
        sys.stdout = original
        configure_logging("INFO")


async def test_issue_19_a_head_request_is_logged_with_its_route_and_method() -> None:
    """The middleware passed a copy of the request on, so the router recorded the route
    it matched on the copy and the access log, reading the original, said "(unmatched)".
    Monitors use HEAD, and in slice 4 every link-preview bot would have looked like a
    404 in the logs."""
    with capturing_logs() as log_stream:
        app = create_app(_settings())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.head("/api/health/live")

    access = [
        json.loads(line)
        for line in log_stream.getvalue().splitlines()
        if line.strip().startswith("{") and json.loads(line).get("event") == "request"
    ]
    assert len(access) == 1, access
    assert access[0]["route"] == "/api/health/live"
    assert access[0]["method"] == "HEAD", "the access line must say what was asked for"


async def test_issue_19_a_route_can_tell_a_head_request_from_a_get() -> None:
    """CLAUDE.md section 6 requires slice 4 to answer HEAD without counting a click. The
    route has to be able to tell, and with the method rewritten it could not."""
    app = create_app(_settings())
    seen: list[bool] = []

    @app.get("/_probe/head")
    async def probe(request: Request) -> dict[str, str]:
        seen.append(bool(getattr(request.state, "head_request", False)))
        return {"status": "ok"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/_probe/head")
        await client.head("/_probe/head")

    assert seen == [False, True]


def test_issue_20_a_remote_database_with_no_sslmode_still_verifies() -> None:
    """A Neon address copied without its query string connected with unverified TLS and
    fell back to plaintext in silence. Absence is not consent (ADR 0012 rule 3)."""
    _, connect_args = asyncpg_url_and_args("postgresql://u:p@ep-x.neon.tech/neondb")

    context = connect_args["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname


def test_issue_20_a_local_database_is_left_alone() -> None:
    """Development has no TLS at all, so loopback keeps the permissive default."""
    _, connect_args = asyncpg_url_and_args("postgresql://u:p@localhost:5432/urlshortener")

    assert "ssl" not in connect_args


def test_issue_21_a_rejected_setting_never_prints_its_value() -> None:
    """The error text went to the startup log, password and all - issue #17 one layer
    earlier, at the moment most likely to be pasted into a ticket."""
    with pytest.raises(ValidationError) as caught:
        _settings(database_url="postgresql://app:S3CRET@db.example.com/app ")

    assert "S3CRET" not in str(caught.value)


@pytest.mark.parametrize(
    "url",
    [
        pytest.param(
            "postgresql://u:p@localhost:5433,db.prod.example.com:5432/urlshortener_test",
            id="host-list-with-ports",
        ),
        pytest.param("postgresql://u:p@localhost,db.prod.example.com/x_test", id="host-list"),
        pytest.param("postgresql://u:p@localhost:not-a-port/x_test", id="unreadable-port"),
    ],
)
def test_issue_22_a_host_list_cannot_smuggle_a_second_server_past_the_guard(url: str) -> None:
    """libpq and asyncpg try each host in turn. Python reads the host as the text up to
    the first colon, so the guard saw only `localhost` and approved production."""
    with pytest.raises(UnsafeTestDatabaseError):
        ensure_safe_test_database_url(url)


@pytest.mark.parametrize("value", ["inf", "nan", "0", "-5"])
def test_issue_23_an_unusable_connect_timeout_is_refused(value: str) -> None:
    """`0` means "wait forever" to the standard client and "give up at once" to asyncpg."""
    with pytest.raises(ValueError, match="connect_timeout"):
        asyncpg_url_and_args(f"postgresql://u:p@h/db?sslmode=disable&connect_timeout={value}")


def test_issue_24_a_database_url_that_is_not_postgres_is_refused() -> None:
    """It used to be rewritten to postgresql+asyncpg and fail later, further from the
    mistake. Every parameter is checked; the scheme was reinterpreted."""
    with pytest.raises(ValueError, match="mysql"):
        asyncpg_url_and_args("mysql://u:p@h/db")


def test_issue_25_an_invisible_character_anywhere_in_an_origin_is_refused() -> None:
    """A zero-width space survives a copy-paste, is not ASCII whitespace, and leaves the
    frontend blocked by CORS with nothing to explain it."""
    with pytest.raises(ValueError):
        bare_origin("https://app.example.com​")
