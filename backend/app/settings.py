from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    ollama_base_url: str = "http://host.docker.internal:11434"
    model_name: str = "gemma4"
    use_tool_fallback: str = "auto"
    db_pool_min: int = 1
    db_pool_max: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
