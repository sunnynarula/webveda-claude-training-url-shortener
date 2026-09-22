"""Database connection handling (ADR 0010: Neon-style URLs)."""

from sqlalchemy.engine import make_url

# libpq understands these query parameters and asyncpg rejects them.
_LIBPQ_ONLY = ("sslmode", "channel_binding")
# The libpq sslmode values, all of which asyncpg's `ssl` argument accepts as strings.
_SSL_MODES = frozenset({"disable", "allow", "prefer", "require", "verify-ca", "verify-full"})


def asyncpg_url_and_args(url: str) -> tuple[str, dict[str, object]]:
    """Return a `postgresql+asyncpg://` URL without libpq-only query parameters
    (`sslmode`, `channel_binding`), plus the matching `connect_args`."""
    parsed = make_url(url)
    sslmode = parsed.query.get("sslmode")
    connect_args: dict[str, object] = {}
    if sslmode is not None:
        if not isinstance(sslmode, str) or sslmode not in _SSL_MODES:
            raise ValueError("sslmode must appear once, with a libpq sslmode value")
        connect_args["ssl"] = sslmode
    cleaned = parsed.difference_update_query(_LIBPQ_ONLY).set(drivername="postgresql+asyncpg")
    return cleaned.render_as_string(hide_password=False), connect_args
