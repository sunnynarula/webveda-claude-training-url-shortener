"""Settings, read from environment variables (CLAUDE.md §10).

In development a `.env` file in `backend/` is read too. Tests must never read
it: construct `Settings(_env_file=None, ...)` with explicit values.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Origin validation arrives in GREEN."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    redis_url: str
    public_base_url: str
    frontend_origin: str
    log_level: str = "INFO"
    host: str = "127.0.0.1"
    port: int = 8000
