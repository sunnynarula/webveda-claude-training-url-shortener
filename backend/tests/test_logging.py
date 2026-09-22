"""Acceptance test 7 (TASKS.md, slice 1; CLAUDE.md §9): the server writes only JSON log lines.

This runs the real entry point, ``python -m app``, as a separate process, so uvicorn's own
startup and shutdown lines are covered as well as the app's. It is a plain synchronous test,
and it waits for the server inside the test body, so a server that never starts makes the test
fail rather than error.
"""

import contextlib
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
HEALTH = "/api/health/live"
READY_TIMEOUT_S = 10.0
ACCESS_FIELDS = {"request_id", "method", "route", "status", "duration_ms"}


def free_port() -> int:
    """A port nothing is listening on right now, chosen by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


def wait_until_live(server: subprocess.Popen[bytes], http: httpx.Client) -> bool:
    """Poll the liveness route until it answers 200, the server exits, or time runs out."""
    deadline = time.monotonic() + READY_TIMEOUT_S
    while time.monotonic() < deadline:
        if server.poll() is not None:
            return False
        with contextlib.suppress(httpx.TransportError):
            if http.get(HEALTH).status_code == 200:
                return True
        time.sleep(0.1)
    return False


def stop(server: subprocess.Popen[bytes]) -> None:
    if server.poll() is None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait()


def parse_object(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def test_server_logs_only_json_lines_with_one_access_line_per_request(
    tmp_path: Path, settings_values: dict[str, str]
) -> None:
    port = free_port()
    env = {
        **os.environ,  # conftest has already removed the developer's settings variables
        **{name.upper(): value for name, value in settings_values.items()},
        "LOG_LEVEL": "INFO",
        "HOST": "127.0.0.1",
        "PORT": str(port),
    }
    marker = uuid.uuid4().hex  # sent only in the query string, so it must never be logged
    request_id = f"log-smoke-{uuid.uuid4().hex[:12]}"
    log_path = tmp_path / "server.log"

    with log_path.open("wb") as log_file:
        server = subprocess.Popen(
            [sys.executable, "-m", "app"],
            cwd=BACKEND_DIR,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            base_url = f"http://127.0.0.1:{port}"
            with httpx.Client(base_url=base_url, timeout=2.0, trust_env=False) as http:
                live = wait_until_live(server, http)
                assert live, (
                    f"`python -m app` did not answer 200 on {HEALTH} within "
                    f"{READY_TIMEOUT_S:.0f} s (exit code {server.poll()}). Output:\n"
                    + log_path.read_text(encoding="utf-8", errors="replace")
                )
                response = http.get(
                    HEALTH, params={"leak_check": marker}, headers={"X-Request-ID": request_id}
                )
                assert response.status_code == 200
        finally:
            stop(server)

    output = log_path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in output.splitlines() if line.strip()]
    records = [parse_object(line) for line in lines]

    not_json = [line for line, record in zip(lines, records, strict=True) if record is None]
    assert not not_json, "log lines that are not JSON objects:\n" + "\n".join(not_json)

    assert any("Application startup complete" in line for line in lines), (
        "uvicorn's own startup lines are missing:\n" + output
    )

    access = [
        record
        for record in records
        if record and record.get("event") == "request" and record.get("request_id") == request_id
    ]
    assert len(access) == 1, f"want one access line for request {request_id!r}, got {access}"
    entry = access[0]
    assert ACCESS_FIELDS <= entry.keys(), f"lacks {sorted(ACCESS_FIELDS - entry.keys())}: {entry}"
    assert entry["method"] == "GET"
    assert entry["route"] == HEALTH
    assert entry["status"] == 200
    duration = entry["duration_ms"]
    assert isinstance(duration, int | float) and not isinstance(duration, bool), duration
    assert duration >= 0, duration

    leaked = [line for line in lines if marker in line or "leak_check" in line]
    assert not leaked, "the query string reached the logs:\n" + "\n".join(leaked)
