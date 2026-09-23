"""Database connection handling (ADR 0010: Neon-style URLs; ADR 0012: allowlists).

A libpq URL and asyncpg do not agree about query parameters: SQLAlchemy's asyncpg
dialect passes every one of them to `asyncpg.connect`, which has no `**kwargs`, so
anything it does not accept is a TypeError on the first connection in production.
So each parameter here is either translated to its asyncpg equivalent or refused by
name at startup. Nothing is passed through, and nothing is dropped in silence.
"""

import ssl
from urllib.parse import parse_qsl, urlsplit

from sqlalchemy.engine import URL, make_url

# The drivers we accept. Everything else is refused rather than rewritten, so a URL for
# another kind of database fails at startup and names itself (issue #24).
_POSTGRES_DRIVERS = frozenset(
    {"postgres", "postgresql", "postgresql+asyncpg", "postgresql+psycopg", "postgresql+psycopg2"}
)
# Hosts where development runs without TLS at all. Anywhere else, TLS is verified even
# when the URL does not ask for it (issue #20).
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_SSL_MODES = frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"})
# The modes that insist on TLS. For these we verify the server's certificate, which
# libpq's "require" does not do — see the note in ADR 0010 about channel binding.
_TLS_REQUIRED = frozenset({"require", "verify-ca", "verify-full"})


def asyncpg_url_and_args(url: str) -> tuple[URL, dict[str, object]]:
    """Return a `postgresql+asyncpg://` URL with no query string, plus the
    `connect_args` that carry what the query string asked for.

    A `URL` rather than a string, so the password is masked by default wherever the
    value is printed — a log line, a `repr`, a traceback (issue #17). Somewhere that
    genuinely needs the text calls `render_as_string(hide_password=False)` and is
    visible in review; `create_async_engine` takes the object as it is.
    """
    parts = urlsplit(url)
    if parts.scheme not in _POSTGRES_DRIVERS:
        raise ValueError(
            f"{parts.scheme!r} is not a PostgreSQL URL; expected one of "
            f"{', '.join(sorted(_POSTGRES_DRIVERS))}"
        )
    if parts.fragment:
        # libpq has no fragments: everything after '#' is part of the URL to it, and
        # a '?' after it still begins the parameter list (ADR 0012).
        raise ValueError("a database URL must not contain '#'")

    params: dict[str, list[str]] = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        params.setdefault(key, []).append(value)

    def take(name: str) -> str | None:
        """The single value of a parameter we act on. Repeating one is ambiguous —
        libpq's "last one wins" is how `sslmode=require&sslmode=disable` would turn
        TLS off — so a parameter that matters is refused rather than resolved."""
        values = params.pop(name, [])
        if len(values) > 1:
            raise ValueError(f"{name} appears more than once in the database URL")
        return values[0] if values else None

    connect_args: dict[str, object] = {}
    server_settings: dict[str, str] = {}

    # asyncpg cannot do channel binding at all: its SCRAM client hard-codes "n,,". This
    # one is discarded however often it appears, and losing it is why the TLS handling
    # below verifies the server's certificate (ADR 0010, issue #15).
    params.pop("channel_binding", None)

    sslmode = take("sslmode")
    if sslmode is not None and sslmode not in _SSL_MODES:
        raise ValueError(f"sslmode must be one of {', '.join(sorted(_SSL_MODES))}")
    if sslmode in _TLS_REQUIRED or (sslmode is None and parts.hostname not in _LOCAL_HOSTS):
        # Verifies the certificate chain and the hostname against the system trust store.
        # Stricter than libpq's "require", deliberately (issue #15) - and used when the
        # URL says nothing at all, because absence is not consent (issue #20). A server
        # without a public certificate needs an explicit sslmode saying so.
        connect_args["ssl"] = ssl.create_default_context()
    elif sslmode is not None:
        connect_args["ssl"] = sslmode  # disable / allow / prefer keep libpq's meaning

    if (options := take("options")) is not None:
        server_settings["options"] = options
    if (application_name := take("application_name")) is not None:
        server_settings["application_name"] = application_name
    if (connect_timeout := take("connect_timeout")) is not None:
        try:
            seconds = float(connect_timeout)
        except ValueError:
            raise ValueError("connect_timeout must be a number of seconds") from None
        # float() accepts inf and nan, and libpq's 0 means "wait forever" where asyncpg
        # reads it as "give up at once" - the opposite of the intent (issue #23).
        if not 0 < seconds < float("inf"):
            raise ValueError("connect_timeout must be a finite number of seconds above 0")
        connect_args["timeout"] = seconds
    if (session_attrs := take("target_session_attrs")) is not None:
        # asyncpg takes this one under its own name, and validates the value itself.
        connect_args["target_session_attrs"] = session_attrs

    if "sslrootcert" in params:
        # Honouring it would mean reading a file here, so a URL translation would
        # depend on the filesystem and fail at a distance. The deploy target's
        # certificates chain to a public authority; a private CA is a slice 9 decision.
        raise ValueError(
            "sslrootcert is not supported: certificates are verified against the system trust store"
        )
    if params:
        raise ValueError(f"unsupported database URL parameter(s): {', '.join(sorted(params))}")
    if server_settings:
        connect_args["server_settings"] = server_settings

    return make_url(url).set(drivername="postgresql+asyncpg", query={}), connect_args
