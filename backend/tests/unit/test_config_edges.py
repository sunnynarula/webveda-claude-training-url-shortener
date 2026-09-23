"""Settings edge cases beyond the slice 1 contract (implementer's unit tests)."""

import pytest
from pydantic import ValidationError

from app.config import Settings, bare_origin

REQUIRED = {
    "database_url": "postgresql://u:p@localhost/db",
    "redis_url": "redis://localhost:6379/0",
    "public_base_url": "https://sho.rt",
    "frontend_origin": "https://app.sho.rt",
}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LOG_LEVEL", "HOST", "PORT"):
        monkeypatch.delenv(name, raising=False)


def make(**overrides: object) -> Settings:
    return Settings(_env_file=None, **{**REQUIRED, **overrides})


def test_log_level_is_normalised_to_upper_case() -> None:
    assert make(log_level="debug").log_level == "DEBUG"


def test_unknown_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError, match="log_level"):
        make(log_level="verbose")


@pytest.mark.parametrize("port", [0, 65536])
def test_port_out_of_range_is_rejected(port: int) -> None:
    with pytest.raises(ValidationError, match="port"):
        make(port=port)


def test_trailing_slash_is_dropped_from_an_origin() -> None:
    assert bare_origin("https://sho.rt/") == "https://sho.rt"


@pytest.mark.parametrize(
    "value",
    [
        "https://user:pw@sho.rt",  # credentials
        "https://sho.rt:99999",  # port out of range
        "https://sho.rt:http",  # port not a number
        "https://sho.rt#top",  # fragment
        "ftp://sho.rt",  # scheme
        "https://",  # no host
    ],
)
def test_origin_edge_cases_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        bare_origin(value)


def test_http_is_allowed_for_ipv6_loopback() -> None:
    assert bare_origin("http://[::1]:5173") == "http://[::1]:5173"


def test_a_required_setting_padded_with_whitespace_is_rejected() -> None:
    """A .env line written as `DATABASE_URL= postgresql://…` is a typo, not a value."""
    with pytest.raises(ValidationError, match="whitespace"):
        make(database_url=" postgresql://u:p@localhost/db ")
