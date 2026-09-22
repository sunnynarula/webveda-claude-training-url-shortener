"""Held-out tests for the two origin settings (TASKS.md slice 1, acceptance 2).

The contract: `PUBLIC_BASE_URL` and `FRONTEND_ORIGIN` must be bare origins -- a scheme and a
host, an optional port, and no path, query or fragment -- and must be `https`, except that
`http` is allowed for `localhost` and `127.0.0.1`.

`urlsplit` is lenient in ways that matter here: it deletes tabs and newlines from anywhere in
the URL and trims leading control characters before parsing, so a value that parses as a bare
origin is not necessarily *made of* a bare origin. And what the validator returns is the
string the app will later compare against a browser's `Origin` header and paste in front of a
short code, so the value itself has to be usable, not merely parseable.
"""

from collections.abc import Callable

import httpx
import pytest
from asgi_lifespan import LifespanManager
from pydantic import ValidationError

from app.config import Settings
from app.main import create_app

ORIGIN_FIELDS = ["public_base_url", "frontend_origin"]

# Each value parses as an origin only because urlsplit first deletes or trims a character that
# has no business in a configured origin. The stored value keeps that character.
ORIGINS_WITH_CONTROL_CHARACTERS = [
    pytest.param("https://sho.rt\n", id="trailing-newline"),
    pytest.param("https://sho.rt\r", id="trailing-carriage-return"),
    pytest.param("https://sho.rt\t", id="trailing-tab"),
    pytest.param("\nhttps://sho.rt", id="leading-newline"),
    pytest.param("https://exa\tmple.com", id="tab-inside-the-host"),
    pytest.param("https://exa\nmple.com", id="newline-inside-the-host"),
    pytest.param("http://local\thost", id="tab-inside-a-local-host"),
    pytest.param("https://sho.rt ", id="trailing-space"),
    pytest.param(" https://sho.rt", id="leading-space"),
]


@pytest.mark.parametrize("value", ORIGINS_WITH_CONTROL_CHARACTERS)
@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_an_origin_carrying_control_characters_is_a_settings_error(
    make_settings: Callable[..., Settings], field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_an_origin_with_no_port_number_is_a_settings_error(
    make_settings: Callable[..., Settings], field: str
) -> None:
    """Port 0 means "ask the kernel for a free port". It is not an origin a browser or a
    short URL can name."""
    with pytest.raises(ValidationError):
        make_settings(**{field: "https://sho.rt:0"})


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("http://[::1]:5173", id="ipv6-loopback"),
        pytest.param("http://[::1]", id="ipv6-loopback-no-port"),
    ],
)
@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_plain_http_is_allowed_for_the_ipv6_loopback(
    make_settings: Callable[..., Settings], field: str, value: str
) -> None:
    """`::1` is the same machine as `127.0.0.1`, so plain http is allowed there too.

    The held-out run asserted the opposite, because the contract named only `localhost`
    and `127.0.0.1`. Settled in issue #12: the wording changed, the code did not.
    """
    make_settings(**{field: value})


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("", id="empty"),
        pytest.param("   ", id="spaces"),
    ],
)
@pytest.mark.parametrize("field", ["database_url", "redis_url"])
def test_a_required_setting_that_is_present_but_empty_is_a_settings_error(
    make_settings: Callable[..., Settings], field: str, value: str
) -> None:
    """`DATABASE_URL=` in a deployment's environment is a misconfiguration, not a value.
    Caught here it names the variable; caught on first use it is a connection error at the
    first request."""
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


@pytest.mark.parametrize(
    ("configured", "sent"),
    [
        pytest.param("http://LOCALHOST:5173", "http://localhost:5173", id="upper-case-host"),
        pytest.param("https://App.Example.com", "https://app.example.com", id="mixed-case-host"),
    ],
)
async def test_an_origin_is_matched_however_it_was_capitalised(
    make_settings: Callable[..., Settings], configured: str, sent: str
) -> None:
    """A host name is case-insensitive and browsers send it lower-cased. The validator accepts
    an upper-cased host (it lower-cases the host only to *check* it), and the raw string is
    what CORS then compares against, so a capitalised `FRONTEND_ORIGIN` is accepted at boot
    and silently blocks the frontend at runtime."""
    settings = make_settings(frontend_origin=configured)
    app = create_app(settings)

    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/health/live", headers={"Origin": sent})

    assert response.headers.get("access-control-allow-origin") == sent, dict(response.headers)


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        pytest.param("https://sho.rt/", "https://sho.rt", id="trailing-slash"),
        pytest.param("https://sho.rt:8443/", "https://sho.rt:8443", id="port-and-trailing-slash"),
        pytest.param("http://127.0.0.1:8000", "http://127.0.0.1:8000", id="local-ipv4"),
        pytest.param("https://sho.rt:65535", "https://sho.rt:65535", id="highest-port"),
    ],
)
@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_a_bare_origin_is_accepted_and_stored_without_a_trailing_slash(
    make_settings: Callable[..., Settings], field: str, value: str, stored: str
) -> None:
    """Slice 3 joins `PUBLIC_BASE_URL` to a short code, so a stored trailing slash would give
    `https://sho.rt//abc`."""
    settings = make_settings(**{field: value})

    assert getattr(settings, field) == stored


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("https://sho.rt:99999", id="port-out-of-range"),
        pytest.param("https://sho.rt:https", id="named-port"),
        pytest.param("https://u:p@sho.rt", id="credentials"),
        pytest.param("//sho.rt", id="scheme-relative"),
        pytest.param("https:///path", id="no-host"),
        pytest.param("javascript:alert(1)", id="javascript-scheme"),
        pytest.param("data:text/html,x", id="data-scheme"),
        pytest.param("file:///etc/passwd", id="file-scheme"),
        pytest.param("http://127.0.0.1.evil.example", id="local-looking-public-host"),
        pytest.param("http://127.0.0.2", id="other-loopback-address"),
    ],
)
@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_a_value_that_is_not_a_bare_origin_is_a_settings_error(
    make_settings: Callable[..., Settings], field: str, value: str
) -> None:
    with pytest.raises(ValidationError):
        make_settings(**{field: value})


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        pytest.param("debug", "DEBUG", id="lower-case"),
        pytest.param("Warning", "WARNING", id="mixed-case"),
        pytest.param("CRITICAL", "CRITICAL", id="upper-case"),
    ],
)
def test_a_log_level_is_normalised(
    make_settings: Callable[..., Settings], value: str, stored: str
) -> None:
    assert make_settings(log_level=value).log_level == stored


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("TRACE", id="not-a-python-level"),
        pytest.param("20", id="numeric"),
        pytest.param("", id="empty"),
    ],
)
def test_a_log_level_that_is_not_a_level_is_a_settings_error(
    make_settings: Callable[..., Settings], value: str
) -> None:
    """`logging.config` raises at boot for an unknown level, which would make the app fail to
    start with a traceback instead of a settings error."""
    with pytest.raises(ValidationError):
        make_settings(log_level=value)


@pytest.mark.parametrize(
    "value",
    [
        pytest.param(0, id="zero"),
        pytest.param(70000, id="too-large"),
        pytest.param(-1, id="negative"),
    ],
)
def test_a_port_outside_the_tcp_range_is_a_settings_error(
    make_settings: Callable[..., Settings], value: int
) -> None:
    with pytest.raises(ValidationError):
        make_settings(port=value)
