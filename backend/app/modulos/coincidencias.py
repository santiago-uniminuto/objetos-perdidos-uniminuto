"""Bandeja de coincidencias sugeridas por la IA y decisión del admin (HU-06, HU-07).

La IA (agente matcher) solo inserta coincidencias en estado 'sugerida'. Verificar o
rechazar es SIEMPRE una acción de una persona; la base de datos también lo exige.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from psycopg import Connection
from pydantic import BaseModel, Field

from app.db import get_conn
from app.errores import conflicto, no_encontrado
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, ip_cliente, solo_admin

router = APIRouter(prefix="/coincidencias", tags=["coincidencias"])


class Rechazo(BaseModel):
    motivo: str = Field(min_length=3, max_length=300)


@router.get("")
def bandeja(estado: str = Query("sugerida"), limite: int = Query(50, ge=1, le=200),
            u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> dict:
    filas = conn.execute(
        "SELECT co.id, co.creado_en, co.estado, co.puntaje, co.similitud, co.explicacion, co.modelo_llm, "
        "r.id AS reporte_id, r.descripcion_publica AS reporte, r.fecha_perdida, "
        "h.id AS hallazgo_id, h.descripcion_publica AS hallazgo, h.fecha_hallazgo, h.ubicacion_bodega "
        "FROM coincidencia co "
        "JOIN reporte_perdida r ON (r.id, r.creado_en, r.sede_id) = (co.reporte_id, co.reporte_creado_en, co.sede_id) "
        "JOIN hallazgo h ON (h.id, h.creado_en, h.sede_id) = (co.hallazgo_id, co.hallazgo_creado_en, co.sede_id) "
        "WHERE co.sede_id = %s AND co.estado = %s::estado_coincidencia "
        "ORDER BY co.puntaje DESC, co.creado_en DESC LIMIT %s",
        (u.sede_id, estado, limite),
    ).fetchall()
    return {"items": filas}


def _tomar(conn: Connection, coincidencia_id: UUID, sede_id: int) -> dict:
    fila = conn.execute(
        "SELECT * FROM coincidencia WHERE id = %s AND sede_id = %s FOR UPDATE", (coincidencia_id, sede_id)
    ).fetchone()
    if not fila:
        raise no_encontrado("La coincidencia")
    if fila["estado"] != "sugerida":
        raise conflicto(f"La coincidencia ya está '{fila['estado']}'", {"estado": fila["estado"]})
    return fila


@router.post("/{coincidencia_id}/verificar")
def verificar(coincidencia_id: UUID, request: Request, u: Usuario = Depends(solo_admin),
              conn: Connection = Depends(get_conn)) -> dict:
    co = _tomar(conn, coincidencia_id, u.sede_id)
    cerrados = conn.execute(
        "SELECT (SELECT estado::text FROM reporte_perdida WHERE id = %s AND creado_en = %s) AS reporte, "
        "(SELECT estado::text FROM hallazgo WHERE id = %s AND creado_en = %s) AS hallazgo",
        (co["reporte_id"], co["reporte_creado_en"], co["hallazgo_id"], co["hallazgo_creado_en"]),
    ).fetchone()
    if cerrados["reporte"] not in ("publicado", "en_coincidencia") or \
            cerrados["hallazgo"] not in ("publicado", "en_coincidencia"):
        raise conflicto("El reporte o el hallazgo ya no está disponible", cerrados)

    conn.execute("UPDATE coincidencia SET estado = 'verificada', decidido_por = %s, decidido_en = now() "
                 "WHERE id = %s AND sede_id = %s", (u.id, coincidencia_id, u.sede_id))
    conn.execute("UPDATE reporte_perdida SET estado = 'en_coincidencia', actualizado_en = now() "
                 "WHERE id = %s AND creado_en = %s", (co["reporte_id"], co["reporte_creado_en"]))
    conn.execute("UPDATE hallazgo SET estado = 'en_coincidencia', actualizado_en = now() "
                 "WHERE id = %s AND creado_en = %s", (co["hallazgo_id"], co["hallazgo_creado_en"]))
    # El agente notificador escucha este evento para avisar al dueño (si dio consentimiento)
    publicar_evento(conn, "coincidencia", coincidencia_id, u.sede_id, "coincidencia.verificada", {
        "id": str(coincidencia_id), "reporte_id": str(co["reporte_id"]), "hallazgo_id": str(co["hallazgo_id"]),
        "puntaje": float(co["puntaje"]),
    })
    auditar(conn, u.id, "actualizar", "coincidencia", coincidencia_id, u.sede_id, ip=ip_cliente(request),
            detalle={"decision": "verificada"})
    return {"id": coincidencia_id, "estado": "verificada"}


@router.post("/{coincidencia_id}/rechazar")
def rechazar(coincidencia_id: UUID, datos: Rechazo, request: Request, u: Usuario = Depends(solo_admin),
             conn: Connection = Depends(get_conn)) -> dict:
    co = _tomar(conn, coincidencia_id, u.sede_id)
    conn.execute("UPDATE coincidencia SET estado = 'rechazada', decidido_por = %s, decidido_en = now(), "
                 "motivo_rechazo = %s WHERE id = %s AND sede_id = %s",
                 (u.id, datos.motivo, coincidencia_id, u.sede_id))
    # El rechazo alimenta la evaluación de la IA y la memoria del matcher (no vuelve a sugerir el par)
    publicar_evento(conn, "coincidencia", coincidencia_id, u.sede_id, "coincidencia.rechazada",
                    {"id": str(coincidencia_id), "puntaje": float(co["puntaje"])})
    auditar(conn, u.id, "actualizar", "coincidencia", coincidencia_id, u.sede_id, ip=ip_cliente(request),
            detalle={"decision": "rechazada"})
    return {"id": coincidencia_id, "estado": "rechazada"}
