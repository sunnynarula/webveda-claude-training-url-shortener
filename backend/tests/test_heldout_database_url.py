"""Held-out tests for `asyncpg_url_and_args` (TASKS.md slice 1, acceptance 4; ADR 0010).

The job of the function is not only to return a `postgresql+asyncpg://` URL: it is to return
one that asyncpg will actually accept the first time the pool opens a connection. SQLAlchemy's
asyncpg dialect builds its connect keywords as `url.translate_connect_args()` updated with
*every remaining query parameter* (`create_connect_args` in
`sqlalchemy/dialects/postgresql/asyncpg.py`), and `asyncpg.connect` has no `**kwargs`. So any
libpq-only parameter left in the query is a `TypeError` at the first query, in production,
long after `create_async_engine` accepted the URL.

These tests therefore check the connect keywords the dialect *would* pass, not just the ones
this function returns, and they do it without connecting.
"""

import inspect
from urllib.parse import quote

import asyncpg
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import asyncpg_url_and_args

NEON = "postgresql://user:pw@ep-x-pooler.us-east-1.aws.neon.tech/neondb"
# Every keyword asyncpg.connect accepts, plus the four SQLAlchemy's adapter consumes itself.
ASYNCPG_CONNECT_ARGS = frozenset(inspect.signature(asyncpg.connect).parameters)
SQLALCHEMY_ADAPTER_ARGS = frozenset(
    {
        "async_fallback",
        "async_creator_fn",
        "prepared_statement_cache_size",
        "prepared_statement_name_func",
    }
)
TLS_REQUIRED_MODES = ("require", "verify-ca", "verify-full")


def connect_keywords(url: str, connect_args: dict[str, object]) -> set[str]:
    """The keyword names SQLAlchemy's asyncpg dialect would hand to `asyncpg.connect`."""
    engine = create_async_engine(url, connect_args=connect_args)  # builds only, never connects
    _, options = engine.dialect.create_connect_args(engine.url)
    return set(options)


@pytest.mark.parametrize(
    "parameter",
    [
        # Neon's own documentation adds this one for drivers that cannot use SNI.
        pytest.param("options=endpoint%3Dep-x-pooler", id="options"),
        pytest.param("application_name=url-shortener", id="application_name"),
        pytest.param("connect_timeout=10", id="connect_timeout"),
        pytest.param("sslrootcert=%2Fetc%2Fssl%2Fca.pem", id="sslrootcert"),
        pytest.param("target_session_attrs=read-write", id="target_session_attrs"),
    ],
)
def test_no_libpq_only_parameter_survives_into_asyncpg_connect(parameter: str) -> None:
    raw = f"{NEON}?sslmode=require&channel_binding=require&{parameter}"

    url, connect_args = asyncpg_url_and_args(raw)

    unknown = connect_keywords(url, connect_args) - ASYNCPG_CONNECT_ARGS - SQLALCHEMY_ADAPTER_ARGS
    assert not unknown, f"asyncpg.connect would raise TypeError for {sorted(unknown)}"


@pytest.mark.parametrize(
    "query",
    [
        pytest.param("sslmode=", id="empty-value"),
        pytest.param("sslmode=%20require", id="padded-value"),
        pytest.param("sslmode=yes", id="not-a-libpq-value"),
        pytest.param("sslmode=REQUIRE", id="upper-case-value"),
        pytest.param("sslmode=require&sslmode=disable", id="repeated-conflicting"),
        pytest.param("sslmode=require&sslmode=require", id="repeated-identical"),
    ],
)
def test_an_sslmode_that_is_not_one_clear_value_is_refused(query: str) -> None:
    """Silently ignoring an sslmode nobody can read is the worst outcome available: the URL
    asked for TLS and the connection would be made without it."""
    with pytest.raises(ValueError, match="sslmode"):
        asyncpg_url_and_args(f"{NEON}?{query}")


@pytest.mark.parametrize("mode", TLS_REQUIRED_MODES)
def test_the_error_for_a_bad_url_never_prints_the_credentials(mode: str) -> None:
    """A connection URL is a secret. It should not reach a traceback, a log or a CI console."""
    with pytest.raises(ValueError) as caught:
        asyncpg_url_and_args(f"postgresql://user:hunter2@host/db?sslmode={mode}x")

    assert "hunter2" not in str(caught.value), str(caught.value)


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("p@ss/word", id="at-and-slash"),
        pytest.param("p ss", id="space"),
        pytest.param("p+ss", id="plus"),
        pytest.param("p#ss", id="hash"),
        pytest.param("p?ss", id="question-mark"),
        pytest.param("p%ss", id="per-cent"),
        pytest.param("p:ss", id="colon"),
        pytest.param("pä-ss", id="non-ascii"),
        pytest.param("p&sslmode=disable", id="ampersand-that-looks-like-a-parameter"),
    ],
)
def test_a_password_needing_escapes_survives_the_translation(raw: str) -> None:
    """The password is decoded when the URL is parsed and re-encoded when it is rendered. If
    the two do not agree the app authenticates with the wrong string -- or, for the last case,
    grows an extra query parameter."""
    url, connect_args = asyncpg_url_and_args(
        f"postgresql://user:{quote(raw, safe='')}@localhost:5432/db?sslmode=require"
    )

    parsed = make_url(url)
    assert parsed.password == raw, url
    assert parsed.query == {}, f"query left in {url}"
    assert connect_args.get("ssl") == "require", connect_args
    assert create_async_engine(url, connect_args=connect_args).url.password == raw


@pytest.mark.parametrize(
    "drivername",
    [
        pytest.param("postgres", id="heroku-style-postgres"),
        pytest.param("postgresql", id="postgresql"),
        pytest.param("postgresql+psycopg", id="psycopg"),
        pytest.param("postgresql+psycopg2", id="psycopg2"),
        pytest.param("postgresql+asyncpg", id="already-asyncpg"),
    ],
)
def test_any_postgres_driver_prefix_becomes_asyncpg(drivername: str) -> None:
    """`postgres://` is what Neon, Heroku and Render put on the clipboard."""
    raw = f"{drivername}://u:p@localhost:5432/db?sslmode=require"

    url, connect_args = asyncpg_url_and_args(raw)

    assert make_url(url).drivername == "postgresql+asyncpg", url
    assert connect_args.get("ssl") == "require", connect_args


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("postgresql://u:p@[::1]:5432/db?sslmode=require", id="ipv6-host"),
        pytest.param("postgresql://u:p@localhost/db?sslmode=require", id="no-port"),
        pytest.param("postgresql://u:p@localhost:5432/?sslmode=require", id="no-database"),
        pytest.param("postgresql://localhost:5432/db?sslmode=require", id="no-credentials"),
        pytest.param(
            "postgresql://u:p@localhost/db_with_%20space?sslmode=require", id="odd-dbname"
        ),
    ],
)
def test_an_unusual_but_valid_url_keeps_its_parts(raw: str) -> None:
    """Whatever else changes, host, port and database name must come through untouched: this
    function decides which server the app talks to."""
    before = make_url(raw)

    url, _ = asyncpg_url_and_args(raw)

    after = make_url(url)
    assert (after.host, after.port, after.database) == (before.host, before.port, before.database)
    assert (after.username, after.password) == (before.username, before.password)


@pytest.mark.parametrize(
    "query",
    [
        pytest.param("channel_binding=require", id="alone"),
        pytest.param("sslmode=require&channel_binding=require", id="neon-shaped"),
        pytest.param("channel_binding=prefer&channel_binding=require", id="repeated"),
    ],
)
def test_channel_binding_is_always_removed(query: str) -> None:
    """asyncpg cannot do channel binding at all (ADR 0010), so the parameter has to go or the
    first connection fails. Dropping it is a known, recorded loss of protection."""
    url, _ = asyncpg_url_and_args(f"{NEON}?{query}")

    assert "channel_binding" not in url
    assert make_url(url).query == {}
