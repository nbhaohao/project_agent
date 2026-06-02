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

    # LLM — reuse my-agent DeepSeek config (ANTHROPIC_BASE_URL points to DeepSeek)
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    model_id: str = "deepseek-v4-flash"

    # file_read tool: restrict reads to this directory
    tool_fs_root: str = "/tmp/agent_files"

    # Embedding — OpenAI-compatible /embeddings endpoint (SiliconFlow bge-m3 by default)
    embedding_api_key: str = ""
    embedding_base_url: str = "https://api.siliconflow.cn/v1"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024


settings = Settings()
