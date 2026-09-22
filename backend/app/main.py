"""Application factory. Run with `python -m app` (JSON logs) or
`uvicorn app.main:create_app --factory`."""

from fastapi import FastAPI

from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Middleware, error handlers and routes arrive in GREEN."""
    return FastAPI()
