"""Database connection handling (ADR 0010: Neon-style URLs)."""


def asyncpg_url_and_args(url: str) -> tuple[str, dict[str, object]]:
    """Return a `postgresql+asyncpg://` URL without libpq-only query parameters
    (`sslmode`, `channel_binding`), plus the matching `connect_args`."""
    raise NotImplementedError
