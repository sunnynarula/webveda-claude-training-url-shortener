"""Health endpoints: /api/health/live (no dependency checks). /api/health arrives in slice 6."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness: the process is up and serving. Checks no dependencies."""
    return {"status": "ok"}
