"""Application factory. Run with `python -m app` (JSON logs) or
`uvicorn app.main:create_app --factory`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.errors import install_error_handlers
from app.logging_config import configure_logging
from app.middleware import CatchAllMiddleware, RequestIdMiddleware
from app.routers import health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Without explicit settings, they're read from the environment."""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="URL Shortener")
    app.state.settings = settings
    install_error_handlers(app)
    app.include_router(health.router)

    # Each add_middleware call wraps the previous ones, so the last one added is outermost:
    # RequestId, then CORS, then CatchAll. A 500 from CatchAll still gets both headers.
    app.add_middleware(CatchAllMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    return app
