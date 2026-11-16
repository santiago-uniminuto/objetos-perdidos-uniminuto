"""Configuración leída de variables de entorno (.env). Ver .env.example."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

CLAVE_DE_EJEMPLO = "cambia-esto"  # noqa: S105 - valor de .env.example; producción no arranca con él


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "desarrollo"
    database_url: str = "postgresql://app:app@localhost:5432/objetos_perdidos"
    # Conexiones a PostgreSQL. Las peticiones toman antes un cupo (db_pool_max - 2): ver app/db.py (Fase 6).
    db_pool_max: int = 20
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

    # Correo (restablecer contraseña) y URL pública con la que se arman los enlaces
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_tls: bool = False
    smtp_from: str = "Objetos Perdidos UNIMINUTO <no-reply@objetos-perdidos.local>"
    url_publica: str = "http://localhost:8080"
    correo_dominios_permitidos: str = ""   # "uniminuto.edu,uniminuto.edu.co"; vacío = sin restricción
    restablecer_minutos: int = 30
    contrasena_min: int = 12

    dias_custodia: int = 90
    analista_horas: float = 6   # mismo ANALISTA_HORAS que usan los agentes: la API calcula la próxima corrida
    version_aviso_privacidad: str = "2026-11-v1"


    def validar_produccion(self) -> list[str]:
        """Revisión al arrancar fuera de desarrollo (Fase 7). Lo inseguro detiene la API; lo dudoso se avisa.

        Devuelve los avisos (main.py los registra en el log).
        """
        if self.app_env == "desarrollo":
            return []
        if self.secret_key == CLAVE_DE_EJEMPLO or len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY de ejemplo o muy corta: genera una con secrets.token_urlsafe(48)")
        if not self.cookie_segura:
            raise RuntimeError("COOKIE_SEGURA=false en producción: la sesión viajaría sin HTTPS")
        avisos = []
        if not self.url_publica.startswith("https://"):
            avisos.append(f"URL_PUBLICA no es https ({self.url_publica}): los enlaces de los correos no servirán "
                          "desde fuera del portátil")
        if self.limite_publico_por_minuto > 600:
            avisos.append(f"LIMITE_PUBLICO_POR_MINUTO={self.limite_publico_por_minuto}: parece un valor de pruebas "
                          "de carga; en producción va 60")
        if self.smtp_host == "mailpit":
            avisos.append("SMTP_HOST=mailpit: los correos no salen del portátil (Mailpit solo los atrapa)")
        if not self.correo_dominios_permitidos.strip():
            avisos.append("CORREO_DOMINIOS_PERMITIDOS vacío: se acepta y se escribe a cualquier dominio; "
                          "en producción va uniminuto.edu,uniminuto.edu.co")
        return avisos


@lru_cache
def get_settings() -> Settings:
    return Settings()
