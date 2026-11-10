"""Auditoría (ADR-008) y outbox (ADR-004): se escriben en la MISMA transacción del cambio."""

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


def auditar(conn: Connection, usuario_id: UUID | None, accion: str, entidad: str,
            entidad_id: UUID | None = None, sede_id: int | None = None, motivo: str | None = None,
            ip: str | None = None, detalle: dict | None = None) -> None:
    """Registra quién hizo qué. `detalle` nunca lleva datos personales."""
    conn.execute(
        "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id, sede_id, motivo, ip, detalle) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (usuario_id, accion, entidad, entidad_id, sede_id, motivo, ip, Jsonb(detalle or {})),
    )


def publicar_evento(conn: Connection, agregado: str, agregado_id: UUID, sede_id: int | None,
                    tipo_evento: str, payload: dict) -> None:
    """Evento para el ETL y los agentes. Solo ids y campos del objeto: sin datos personales."""
    conn.execute(
        "INSERT INTO outbox (agregado, agregado_id, sede_id, tipo_evento, payload) VALUES (%s, %s, %s, %s, %s)",
        (agregado, agregado_id, sede_id, tipo_evento, Jsonb(payload)),
    )
