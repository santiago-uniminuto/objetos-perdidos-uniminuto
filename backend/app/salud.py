"""Endpoints de salud: /salud (la API responde) y /salud/dependencias (bases y caché)."""

import time

import psycopg
import redis
from fastapi import APIRouter, Response, status

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["salud"])


@router.get("/salud")
def salud() -> dict:
    """La API está viva. No toca dependencias: sirve para el healthcheck del proxy."""
    return {"estado": "ok", "version": __version__, "entorno": get_settings().app_env}


def _medir(fn) -> dict:
    inicio = time.perf_counter()
    try:
        fn()
        return {"estado": "ok", "ms": round((time.perf_counter() - inicio) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001 - se reporta el tipo, nunca el detalle (puede traer credenciales)
        return {"estado": "error", "error": type(exc).__name__}


@router.get("/salud/dependencias")
def salud_dependencias(response: Response) -> dict:
    """Comprueba PostgreSQL (con pgvector) y Redis."""
    cfg = get_settings()

    def postgres() -> None:
        with psycopg.connect(cfg.database_url, connect_timeout=3) as conn:
            conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector'").fetchone()

    def cache() -> None:
        redis.Redis.from_url(cfg.redis_url, socket_timeout=3).ping()

    resultado = {"postgres": _medir(postgres), "redis": _medir(cache)}
    if any(r["estado"] != "ok" for r in resultado.values()):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return resultado
