"""Acceso a PostgreSQL con psycopg 3 y SQL explícito (sin ORM).

Cada petición recibe UNA conexión dentro de UNA transacción: si la petición termina
bien se confirma (commit); si lanza una excepción se revierte. Así el cambio de negocio,
su evento en el outbox y su registro de auditoría se guardan juntos o no se guarda nada.
"""

from collections.abc import Iterator

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import get_settings

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            get_settings().database_url, min_size=1, max_size=10, open=True,
            kwargs={"row_factory": dict_row, "autocommit": False},
        )
    return _pool


def cerrar_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[Connection]:
    """Dependencia de FastAPI: una transacción por petición."""
    with pool().connection() as conn:
        with conn.transaction():
            yield conn
