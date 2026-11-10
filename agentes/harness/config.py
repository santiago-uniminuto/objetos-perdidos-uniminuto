"""Configuración de los agentes por variables de entorno (mismas del .env del proyecto)."""

import os
from dataclasses import dataclass, field


def _env(nombre: str, defecto: str) -> str:
    return os.environ.get(nombre, defecto)


@dataclass(frozen=True)
class Config:
    database_url: str = field(default_factory=lambda: _env(
        "DATABASE_URL", "postgresql://app:app@localhost:5432/objetos_perdidos"))
    redis_url: str = field(default_factory=lambda: _env("REDIS_URL", "redis://localhost:6379/0"))
    mongo_url: str = field(default_factory=lambda: _env("MONGO_URL", ""))
    mongo_db: str = field(default_factory=lambda: _env("MONGO_DB", "objetos_perdidos"))
    # llm = normaliza con Qwen; heuristica = sin LLM (respaldo o si el set humano dice que rinde igual)
    normalizador: str = field(default_factory=lambda: _env("MATCHER_NORMALIZADOR", "llm"))
    explicar: bool = field(default_factory=lambda: _env("MATCHER_EXPLICAR", "true").lower() == "true")
    smtp_host: str = field(default_factory=lambda: _env("SMTP_HOST", "mailpit"))
    smtp_port: int = field(default_factory=lambda: int(_env("SMTP_PORT", "1025")))
    smtp_user: str = field(default_factory=lambda: _env("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: _env("SMTP_PASSWORD", ""))
    smtp_tls: bool = field(default_factory=lambda: _env("SMTP_TLS", "false").lower() == "true")
    smtp_from: str = field(default_factory=lambda: _env(
        "SMTP_FROM", "Objetos Perdidos UNIMINUTO <no-reply@objetos-perdidos.local>"))
    # Analista: cada cuántas horas escribe informes (0 = nunca) y si el resumen lo redacta el LLM
    analista_horas: float = field(default_factory=lambda: float(_env("ANALISTA_HORAS", "6")))
    analista_llm: bool = field(default_factory=lambda: _env("ANALISTA_LLM", "true").lower() == "true")
    intervalo_segundos: float = field(default_factory=lambda: float(_env("AGENTES_INTERVALO", "2")))
