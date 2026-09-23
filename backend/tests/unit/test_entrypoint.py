"""`python -m app` starts uvicorn with our settings and our JSON log config.

The acceptance test for logging runs the entry point in a subprocess, where coverage
can't see it, and a subprocess can't show which arguments uvicorn was given.
"""

from typing import Any

import pytest

import app.__main__ as entrypoint

ENVIRONMENT = {
    "DATABASE_URL": "postgresql://u:p@localhost/db",
    "REDIS_URL": "redis://localhost:6379/0",
    "PUBLIC_BASE_URL": "https://sho.rt",
    "FRONTEND_ORIGIN": "https://app.sho.rt",
    "LOG_LEVEL": "warning",
    "HOST": "127.0.0.1",
    "PORT": "9123",
}


def test_main_serves_the_factory_with_json_logs_and_no_uvicorn_access_log(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name, value in ENVIRONMENT.items():
        monkeypatch.setenv(name, value)
    captured: dict[str, Any] = {}

    def fake_run(target: str, **kwargs: Any) -> None:
        captured.update(kwargs, target=target)

    configured: list[str] = []
    monkeypatch.setattr(entrypoint, "configure_logging", configured.append)
    monkeypatch.setattr(entrypoint.uvicorn, "run", fake_run)

    entrypoint.main()

    # Issue #18: this process is ours, so we configure logging, and tell uvicorn not to.
    assert configured == ["WARNING"]

    assert captured["target"] == "app.main:create_app"
    assert captured["factory"] is True
    assert (captured["host"], captured["port"]) == ("127.0.0.1", 9123)
    assert captured["log_config"] is None
    assert captured["log_level"] == "warning"
    # uvicorn's own access line carries the query string; app.middleware logs the route instead.
    assert captured["access_log"] is False
    # Don't advertise the server and its version to every client.
    assert captured["server_header"] is False
