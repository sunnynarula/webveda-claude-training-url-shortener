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


def test_other_query_parameters_are_kept() -> None:
    url, _ = asyncpg_url_and_args("postgresql://u:p@h/db?sslmode=require&application_name=x")
    assert url == "postgresql+asyncpg://u:p@h/db?application_name=x"


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
