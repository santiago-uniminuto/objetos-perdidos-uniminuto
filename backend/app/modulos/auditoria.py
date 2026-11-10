"""GET /auditoria: bitácora de accesos para el rol auditor (HU-14)."""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from psycopg import Connection

from app.db import get_conn
from app.seguridad import Usuario, codificar_cursor, decodificar_cursor, solo_auditor

router = APIRouter(prefix="/auditoria", tags=["auditoría"])


@router.get("")
def consultar(usuario: UUID | None = None, entidad: str | None = None, entidad_id: UUID | None = None,
              accion: str | None = None, desde: date | None = None, hasta: date | None = None,
              cursor: str | None = None, limite: int = Query(50, ge=1, le=200),
              _: Usuario = Depends(solo_auditor), conn: Connection = Depends(get_conn)) -> dict:
    filtros, params = ["true"], []
    for columna, valor in (("a.usuario_id", usuario), ("a.entidad", entidad), ("a.entidad_id", entidad_id)):
        if valor is not None:
            filtros.append(f"{columna} = %s")
            params.append(valor)
    if accion:
        filtros.append("a.accion = %s::accion_auditoria")
        params.append(accion)
    if desde:
        filtros.append("a.creado_en >= %s")
        params.append(desde)
    if hasta:
        filtros.append("a.creado_en < %s::date + 1")
        params.append(hasta)
    if cursor:
        c_fecha, c_id = decodificar_cursor(cursor)
        filtros.append("(a.creado_en, a.id) < (%s, %s)")
        params += [c_fecha, c_id.int]
    filas = conn.execute(
        "SELECT a.id, a.creado_en, a.accion, a.entidad, a.entidad_id, a.sede_id, a.motivo, a.ip::text AS ip, "
        "a.detalle, u.nombre AS usuario FROM auditoria a LEFT JOIN usuario u ON u.id = a.usuario_id WHERE "
        + " AND ".join(filtros) + " ORDER BY a.creado_en DESC, a.id DESC LIMIT %s",
        [*params, limite + 1],
    ).fetchall()
    siguiente = None
    if len(filas) > limite:
        ultimo = filas[limite - 1]
        # el id de auditoría es numérico: se empaqueta en un UUID para reutilizar el formato de cursor
        siguiente = codificar_cursor(ultimo["creado_en"], UUID(int=ultimo["id"]))
    return {"items": filas[:limite], "siguiente": siguiente}
