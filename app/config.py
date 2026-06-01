"""Cross-cutting application settings, loaded from environment / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "project_agent"
    # postgresql+asyncpg://user:pass@host:port/db
    database_url: str = "postgresql+asyncpg://agent:agent@localhost:5432/agent"
    redis_url: str = "redis://localhost:6379/0"


settings = Settings()
