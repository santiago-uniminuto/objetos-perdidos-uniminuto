"""Acceso a PostgreSQL con psycopg 3 y SQL explícito (sin ORM).

Cada petición recibe UNA conexión dentro de UNA transacción: si la petición termina
bien se confirma (commit); si lanza una excepción se revierte. Así el cambio de negocio,
su evento en el outbox y su registro de auditoría se guardan juntos o no se guarda nada.
"""

import asyncio
import weakref
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager

import anyio
from fastapi import Depends
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url, min_size=2, max_size=get_settings().db_pool_max, open=True,
            kwargs={"row_factory": dict_row, "autocommit": False},
        )
    return _pool


def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


# ---------------------------------------------------------------- cupos (hallazgo de la Fase 6)
# FastAPI saca la conexión en un hilo, lo suelta y pide OTRO hilo para la ruta. Bajo carga podía pasar que
# todos los hilos esperaran conexión mientras todas las conexiones esperaban hilo: la API se congelaba
# hasta el PoolTimeout (30 s). Ahora cada petición toma primero un CUPO asíncrono (esperar uno no ocupa
# hilo ni conexión) y hay menos cupos que conexiones: quien tiene cupo siempre encuentra conexión.
RESERVA_CONEXIONES = 2  # para lo que usa el pool fuera de una petición (purga de fotos) y margen
_cupos: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, anyio.Semaphore]" = weakref.WeakKeyDictionary()


def _semaforo() -> anyio.Semaphore:
    bucle = asyncio.get_running_loop()  # uno por bucle de eventos (en producción hay uno solo)
    if bucle not in _cupos:
        _cupos[bucle] = anyio.Semaphore(max(1, get_settings().db_pool_max - RESERVA_CONEXIONES))
    return _cupos[bucle]


@asynccontextmanager
async def cupo() -> AsyncIterator[None]:
    """Para código async que llama a la base desde un hilo (p. ej. el login)."""
    async with _semaforo():
        yield


async def cupo_bd() -> AsyncIterator[None]:
    """Dependencia: toda ruta que use PostgreSQL la recibe (get_conn la incluye)."""
    async with _semaforo():
        yield


def get_conn(_cupo: None = Depends(cupo_bd)) -> Iterator[Connection]:
    """Dependencia de FastAPI: una transacción por petición (después de tomar un cupo)."""
    with pool().connection() as conn:
        with conn.transaction():
            yield conn
