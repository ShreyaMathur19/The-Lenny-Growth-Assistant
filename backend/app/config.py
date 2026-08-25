from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "The Lenny Growth Assistant"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://postgres:postgres@postgres:5432/lenny"
    agent_service_url: str = "http://agent:3001"
    ollama_base_url: str = "http://ollama:11434"
    ollama_chat_model: str = "llama3.2:3b"
    ollama_embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768
    top_k: int = 6
    max_history_messages: int = 12
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:5173,http://localhost:4173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
