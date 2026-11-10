"""Configuración leída de variables de entorno (.env). Ver .env.example."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

CLAVE_DE_EJEMPLO = "cambia-esto"  # noqa: S105 - valor de .env.example; producción no arranca con él


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "desarrollo"
    database_url: str = "postgresql://app:app@localhost:5432/objetos_perdidos"
    redis_url: str = "redis://localhost:6379/0"

    # Seguridad
    secret_key: str = CLAVE_DE_EJEMPLO
    sesion_minutos: int = 30
    cookie_segura: bool = True          # la cookie solo viaja por HTTPS (Funnel); localhost también cuenta
    max_intentos_login: int = 5
    bloqueo_minutos: int = 15
    limite_publico_por_minuto: int = 60
    cache_publico_segundos: int = 30

    # IA: chat y embeddings son proveedores independientes (ADR-005)
    llm_provider: str = "ollama"
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_model: str = "qwen2.5:3b"
    embedding_provider: str = "ollama"
    embedding_model: str = "bge-m3"
    embedding_dim: int = 1024

    dias_custodia: int = 90
    version_aviso_privacidad: str = "2026-11-v1"


    def validar_produccion(self) -> None:
        """Fuera de desarrollo, la API no arranca con la clave de ejemplo ni con una clave corta."""
        if self.app_env != "desarrollo" and (self.secret_key == CLAVE_DE_EJEMPLO or len(self.secret_key) < 32):
            raise RuntimeError("SECRET_KEY de ejemplo o muy corta: genera una con secrets.token_urlsafe(48)")


@lru_cache
def get_settings() -> Settings:
    return Settings()
