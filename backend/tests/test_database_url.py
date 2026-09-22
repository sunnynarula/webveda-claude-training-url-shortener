"""Acceptance test 4 (TASKS.md, slice 1; ADR 0010): Neon-style URLs are made safe for asyncpg.

libpq-style URLs carry TLS settings in the query string (``sslmode``, ``channel_binding``).
SQLAlchemy passes query parameters on to ``asyncpg.connect`` as keyword arguments, and
``asyncpg.connect`` accepts neither, so the first connection would fail with a TypeError.
``create_async_engine`` on its own can't show this, because it never connects: it accepts the
raw Neon URL too. So the tests also check each connect argument against asyncpg's signature.
"""

import inspect
import ssl
from urllib.parse import urlsplit

import asyncpg
import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import asyncpg_url_and_args

NEON_URL = (
    "postgresql://user:pw@ep-x-pooler.us-east-1.aws.neon.tech/neondb"
    "?sslmode={sslmode}&channel_binding=require"
)
LOCAL_URL = "postgresql://u:p@localhost:5432/urlshortener_test"

# Every keyword asyncpg.connect accepts. It has no **kwargs, so anything else is a TypeError.
ASYNCPG_CONNECT_ARGS = frozenset(inspect.signature(asyncpg.connect).parameters)
# Keywords SQLAlchemy's asyncpg adapter consumes itself before it calls asyncpg.connect
# (AsyncAdapt_asyncpg_dbapi.connect in sqlalchemy/dialects/postgresql/asyncpg.py).
SQLALCHEMY_ADAPTER_ARGS = frozenset(
    {
        "async_fallback",
        "async_creator_fn",
        "prepared_statement_cache_size",
        "prepared_statement_name_func",
    }
)
# asyncpg ssl values that insist on TLS. "disable", "allow" and "prefer" can connect in plaintext.
TLS_REQUIRED_MODES = ("require", "verify-ca", "verify-full")


def requires_tls(value: object) -> bool:
    return value is True or isinstance(value, ssl.SSLContext) or value in TLS_REQUIRED_MODES


@pytest.mark.parametrize("sslmode", TLS_REQUIRED_MODES)
def test_neon_url_becomes_asyncpg_url_without_query_and_with_tls(sslmode: str) -> None:
    url, connect_args = asyncpg_url_and_args(NEON_URL.format(sslmode=sslmode))

    assert url.startswith("postgresql+asyncpg://"), url
    assert "?" not in url and urlsplit(url).query == "", f"query string left in {url}"
    parsed = make_url(url)
    assert (parsed.username, parsed.password, parsed.host, parsed.database) == (
        "user",
        "pw",
        "ep-x-pooler.us-east-1.aws.neon.tech",
        "neondb",
    )

    assert requires_tls(connect_args.get("ssl")), f"connect_args don't require TLS: {connect_args}"
    unknown = set(connect_args) - ASYNCPG_CONNECT_ARGS - SQLALCHEMY_ADAPTER_ARGS
    assert not unknown, f"asyncpg.connect would reject {sorted(unknown)}"

    engine = create_async_engine(url, connect_args=connect_args)  # builds only, never connects
    assert engine.url.drivername == "postgresql+asyncpg"


def test_plain_local_url_becomes_asyncpg_url_without_tls() -> None:
    url, connect_args = asyncpg_url_and_args(LOCAL_URL)

    assert url.startswith("postgresql+asyncpg://"), url
    parsed = make_url(url)
    assert (parsed.username, parsed.password, parsed.host, parsed.port, parsed.database) == (
        "u",
        "p",
        "localhost",
        5432,
        "urlshortener_test",
    )
    assert "ssl" not in connect_args, connect_args

    engine = create_async_engine(url, connect_args=connect_args)  # builds only, never connects
    assert engine.url.drivername == "postgresql+asyncpg"
