"""Configuración leída de variables de entorno (.env). Ver .env.example."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "desarrollo"
    database_url: str = "postgresql://app:app@localhost:5432/objetos_perdidos"
    redis_url: str = "redis://localhost:6379/0"

    # IA: chat y embeddings son proveedores independientes (ADR-005)
    llm_provider: str = "ollama"
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_model: str = "qwen2.5:3b"
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    dias_custodia: int = 90


@lru_cache
def get_settings() -> Settings:
    return Settings()
