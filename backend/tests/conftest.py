"""Shared fixtures for the acceptance tests (TASKS.md).

Two rules keep these tests honest:

- Nothing from the developer's environment leaks in. Every test starts with the settings
  variables removed from ``os.environ``, and ``Settings`` is always built with
  ``_env_file=None`` and explicit values, so neither a shell export nor ``backend/.env`` can
  change a result.
- Fixtures only call code that already runs without raising. A fixture that raises makes a
  test ERROR, and a RED test has to FAIL instead.
"""

from collections.abc import AsyncIterator, Callable, Iterable
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI

from app.config import Settings
from app.main import create_app

SETTINGS_ENV_VARS = (
    "DATABASE_URL",
    "REDIS_URL",
    "PUBLIC_BASE_URL",
    "FRONTEND_ORIGIN",
    "LOG_LEVEL",
    "HOST",
    "PORT",
)


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def settings_values() -> dict[str, str]:
    """Valid values for the required settings. They look local, but nothing in slice 1
    connects to Postgres or Redis."""
    return {
        "database_url": "postgresql://u:p@localhost:5432/urlshortener_test",
        "redis_url": "redis://localhost:6379/15",
        "public_base_url": "http://localhost:8000",
        "frontend_origin": "http://localhost:5173",
    }


@pytest.fixture
def make_settings(settings_values: dict[str, str]) -> Callable[..., Settings]:
    """Build ``Settings`` from the valid values, replacing some (keyword arguments) or
    leaving some out (``omit``)."""

    def make(*, omit: Iterable[str] = (), **overrides: Any) -> Settings:
        left_out = set(omit)
        values: dict[str, Any] = {k: v for k, v in settings_values.items() if k not in left_out}
        values.update(overrides)
        return Settings(_env_file=None, **values)

    return make


@pytest.fixture
def settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings()


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client for the app, with the app's lifespan running. An exception inside the
    app comes back as the 500 response a server would send, not as an exception here."""
    async with LifespanManager(app) as manager:
        transport = httpx.ASGITransport(app=manager.app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
