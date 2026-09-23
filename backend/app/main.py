"""Application factory. Run with `python -m app` (JSON logs) or
`uvicorn app.main:create_app --factory`."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.errors import install_error_handlers
from app.logging_config import configure_logging
from app.middleware import CatchAllMiddleware, HeadAsGetMiddleware, RequestIdMiddleware
from app.routers import health


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Without explicit settings, they're read from the environment."""
    settings = settings or Settings()
    configure_logging(settings.log_level)

    # redirect_slashes off: with it on, /path/ is answered by a redirect built from the
    # client's own Host header, carrying the query string back with it, before any route
    # code runs. In slice 4 short codes sit at the root, so that would happen before the
    # code's format is checked. A 404 is the better answer here (issue #10).
    app = FastAPI(title="URL Shortener", redirect_slashes=False)
    app.state.settings = settings
    install_error_handlers(app)
    app.include_router(health.router)

    # Each add_middleware call wraps the previous ones, so the last one added is outermost:
    # RequestId, then CORS, then HeadAsGet, then CatchAll. A 500 from CatchAll still gets
    # both headers, and a HEAD request is stripped of its body after everything else ran.
    app.add_middleware(CatchAllMiddleware)
    app.add_middleware(HeadAsGetMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    app.add_middleware(RequestIdMiddleware)
    return app
