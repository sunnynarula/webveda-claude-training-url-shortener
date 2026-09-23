"""Refuse to run destructive test fixtures against anything but a local `*_test` database.

Our reading of the URL is a guess about what the client will do with it, and the two
disagree in ways that matter: `urlsplit` treats everything after `#` as a fragment,
while libpq has no fragments at all, so `…/x_test#?dbname=postgres` reads as safe here
and sends `psql` to another database. So this guard refuses anything it cannot read
unambiguously, rather than interpreting it (ADR 0012).
"""

from urllib.parse import parse_qsl, unquote, urlsplit

_SAFE_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "postgres"})
# Parameters that cannot change which server or database is reached. Everything else is
# refused by name: a denylist of the dangerous ones only ever catches the ones we thought
# of, and misses the same name in another case (`?HOST=`).
_HARMLESS_PARAMETERS = frozenset({"sslmode", "connect_timeout", "application_name"})


class UnsafeTestDatabaseError(RuntimeError):
    """Raised when TEST_DATABASE_URL could point at real data."""


def ensure_safe_test_database_url(url: str) -> None:
    """Raise UnsafeTestDatabaseError unless the database name ends in `_test` and the
    host is `localhost`, `127.0.0.1`, `::1` or `postgres` (the CI service).

    Messages never include the URL, because they are read in a CI log.
    """
    parts = urlsplit(url)
    if parts.fragment:
        raise UnsafeTestDatabaseError(
            "the test database URL contains '#', which libpq does not treat as a fragment"
        )
    # Exact matches only. libpq's keywords are lower-case, so `?HOST=` is already
    # unusual, and an unusual spelling is a reason to refuse rather than to interpret.
    unexpected = sorted(
        {key for key, _ in parse_qsl(parts.query, keep_blank_values=True)} - _HARMLESS_PARAMETERS
    )
    if unexpected:
        raise UnsafeTestDatabaseError(
            f"the test database URL carries parameter(s) that could change what it "
            f"reaches: {', '.join(unexpected)}"
        )
    if parts.hostname not in _SAFE_HOSTS:
        raise UnsafeTestDatabaseError(
            f"test database host {parts.hostname!r} is not one of {sorted(_SAFE_HOSTS)}"
        )
    name = unquote(parts.path.lstrip("/"))
    if not name.endswith("_test"):
        raise UnsafeTestDatabaseError(f"test database name {name!r} does not end in _test")
