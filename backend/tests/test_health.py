"""Acceptance test 1 (TASKS.md, slice 1): with valid settings the app boots, and the liveness
probe answers."""

import httpx


async def test_app_boots_and_health_live_returns_200_with_request_id(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers.get("x-request-id"), "no X-Request-ID header"
