"""asyncpg_url_and_args edge cases beyond the slice 1 contract."""

import pytest

from app.database import asyncpg_url_and_args


def test_url_without_sslmode_gets_no_connect_args() -> None:
    url, args = asyncpg_url_and_args("postgresql://u:p@localhost:5432/db")
    assert url == "postgresql+asyncpg://u:p@localhost:5432/db"
    assert args == {}


def test_password_survives_the_round_trip() -> None:
    url, _ = asyncpg_url_and_args("postgresql://u:s%40cret@localhost/db")
    assert url == "postgresql+asyncpg://u:s%40cret@localhost/db"


def test_a_parameter_asyncpg_understands_is_translated_not_passed_through() -> None:
    """This test used to assert that unknown parameters were kept in the URL. Issue #11
    showed that SQLAlchemy hands every one of them to asyncpg.connect, which has no
    **kwargs, so keeping them meant a TypeError on the first connection in production."""
    url, args = asyncpg_url_and_args("postgresql://u:p@h/db?sslmode=disable&application_name=x")
    assert url == "postgresql+asyncpg://u:p@h/db"
    assert args["server_settings"] == {"application_name": "x"}


def test_a_parameter_nobody_understands_is_refused() -> None:
    with pytest.raises(ValueError, match="unsupported database URL parameter"):
        asyncpg_url_and_args("postgresql://u:p@h/db?made_up=1")


def test_non_tls_sslmode_passes_through() -> None:
    _, args = asyncpg_url_and_args("postgresql://u:p@h/db?sslmode=disable")
    assert args == {"ssl": "disable"}


@pytest.mark.parametrize(
    "query",
    ["sslmode=bogus", "sslmode=require&sslmode=disable"],
)
def test_unusable_sslmode_is_rejected(query: str) -> None:
    with pytest.raises(ValueError, match="sslmode"):
        asyncpg_url_and_args(f"postgresql://u:p@h/db?{query}")


def test_a_fragment_in_a_database_url_is_refused() -> None:
    """libpq has no fragments, so our reading of the URL and the client's would differ."""
    with pytest.raises(ValueError, match="#"):
        asyncpg_url_and_args("postgresql://u:p@h/db#?dbname=other")


def test_a_connect_timeout_that_is_not_a_number_is_refused() -> None:
    with pytest.raises(ValueError, match="connect_timeout"):
        asyncpg_url_and_args("postgresql://u:p@h/db?connect_timeout=soon")


def test_sslrootcert_is_refused_with_an_explanation() -> None:
    """Honouring it would make this function read a file (issue #15's triage)."""
    with pytest.raises(ValueError, match="system trust store"):
        asyncpg_url_and_args("postgresql://u:p@h/db?sslmode=verify-full&sslrootcert=/ca.pem")
