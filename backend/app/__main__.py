"""`python -m app`: serve the app with uvicorn and JSON logging."""

import uvicorn

from app.config import Settings
from app.logging_config import LOGGING_CONFIG


def main() -> None:
    """Start uvicorn on Settings.host and Settings.port."""
    settings = Settings()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=LOGGING_CONFIG,
        log_level=settings.log_level.lower(),
        access_log=False,  # app.middleware writes the access line, without the query string
        server_header=False,
    )


if __name__ == "__main__":
    main()
