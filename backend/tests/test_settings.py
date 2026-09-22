"""Acceptance tests 2 and 3 (TASKS.md, slice 1): the two origin settings are validated, and
every setting is documented in backend/.env.example."""

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings

BACKEND_DIR = Path(__file__).resolve().parents[1]

ORIGIN_FIELDS = ["public_base_url", "frontend_origin"]

# Each malformed value is paired with a bare origin that differs from it only by the defect.
# The test checks that the bare origin is accepted first, so a rejection can only come from the
# defect, and a validator that rejects everything can't pass.
MALFORMED_ORIGINS = [
    pytest.param("https://sho.rt/links", "https://sho.rt", id="path"),
    pytest.param("https://sho.rt:8443/links", "https://sho.rt:8443", id="path-after-port"),
    pytest.param("https://sho.rt?ref=1", "https://sho.rt", id="query"),
    pytest.param("https://sho.rt#top", "https://sho.rt", id="fragment"),
    pytest.param("ftp://sho.rt", "https://sho.rt", id="ftp-scheme"),
    pytest.param("ws://localhost:5173", "http://localhost:5173", id="ws-scheme-on-local-host"),
    pytest.param("sho.rt", "https://sho.rt", id="no-scheme"),
    pytest.param("", "https://sho.rt", id="empty"),
    pytest.param("http://sho.rt", "https://sho.rt", id="http-for-public-host"),
    pytest.param(
        "http://example.com:5173", "http://127.0.0.1:5173", id="http-for-public-host-with-port"
    ),
    pytest.param("http://localhost.example.com", "http://localhost", id="http-for-lookalike-host"),
    pytest.param("http://localhost@example.com", "http://localhost", id="http-userinfo-hides-host"),
]


@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_missing_origin_setting_is_a_settings_error(
    make_settings: Callable[..., Settings], field: str
) -> None:
    with pytest.raises(ValidationError):
        make_settings(omit=[field])


@pytest.mark.parametrize(("malformed", "bare"), MALFORMED_ORIGINS)
@pytest.mark.parametrize("field", ORIGIN_FIELDS)
def test_malformed_origin_setting_is_a_settings_error(
    make_settings: Callable[..., Settings], field: str, malformed: str, bare: str
) -> None:
    try:
        make_settings(**{field: bare})
    except ValidationError as exc:
        pytest.fail(f"{field}: the bare origin {bare!r} was rejected: {exc}")

    with pytest.raises(ValidationError):
        make_settings(**{field: malformed})


def test_every_setting_appears_in_backend_env_example() -> None:
    env_example = BACKEND_DIR / ".env.example"
    assert env_example.is_file(), "backend/.env.example does not exist"

    text = env_example.read_text(encoding="utf-8")
    # A variable counts when it's assigned, or shown commented out ("# PORT=8000").
    missing = [
        name.upper()
        for name in Settings.model_fields
        if not re.search(rf"^[ \t]*#?[ \t]*{re.escape(name.upper())}[ \t]*=", text, re.MULTILINE)
    ]
    assert not missing, f"settings missing from backend/.env.example: {missing}"
