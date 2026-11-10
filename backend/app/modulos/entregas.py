"""Entrega al dueño (HU-08, HU-09): carné + pregunta de control, acta y cierre del caso."""

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from psycopg import Connection
from pydantic import BaseModel, Field

from app.db import get_conn
from app.errores import conflicto, no_encontrado
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, ip_cliente, solo_admin

router = APIRouter(prefix="/entregas", tags=["entregas"])


class Entrega(BaseModel):
    coincidencia_id: UUID
    verificacion_ok: bool = Field(description="El reclamante mostró carné y respondió bien la pregunta de control")
    numero_acta: str = Field(min_length=3, max_length=40)
    observaciones: str | None = Field(default=None, max_length=500)


@router.post("")
def registrar(datos: Entrega, request: Request, u: Usuario = Depends(solo_admin),
              conn: Connection = Depends(get_conn)) -> dict:
    co = conn.execute(
        "SELECT co.*, r.estudiante_id FROM coincidencia co JOIN reporte_perdida r "
        "ON (r.id, r.creado_en, r.sede_id) = (co.reporte_id, co.reporte_creado_en, co.sede_id) "
        "WHERE co.id = %s AND co.sede_id = %s FOR UPDATE OF co",
        (datos.coincidencia_id, u.sede_id),
    ).fetchone()
    if not co:
        raise no_encontrado("La coincidencia")
    if co["estado"] != "verificada":
        raise conflicto("Solo se entrega un objeto con la coincidencia verificada", {"estado": co["estado"]})

    if not datos.verificacion_ok:
        # No se entrega, pero el intento queda en la auditoría (Fase 1, CU-04 alterno 3a)
        auditar(conn, u.id, "actualizar", "entrega", datos.coincidencia_id, u.sede_id, ip=ip_cliente(request),
                detalle={"resultado": "verificacion_fallida"})
        return {"entregado": False, "motivo": "La verificación del reclamante falló; el objeto sigue en custodia"}

    entrega = conn.execute(
        "INSERT INTO entrega (sede_id, coincidencia_id, estudiante_id, verificacion_ok, numero_acta, observaciones, "
        "registrado_por) VALUES (%s, %s, %s, true, %s, %s, %s) RETURNING id, creado_en",
        (u.sede_id, datos.coincidencia_id, co["estudiante_id"], datos.numero_acta, datos.observaciones, u.id),
    ).fetchone()
    conn.execute("UPDATE coincidencia SET estado = 'entregada' WHERE id = %s AND sede_id = %s",
                 (datos.coincidencia_id, u.sede_id))
    conn.execute("UPDATE reporte_perdida SET estado = 'cerrado', cerrado_en = now(), actualizado_en = now() "
                 "WHERE id = %s AND creado_en = %s", (co["reporte_id"], co["reporte_creado_en"]))
    conn.execute("UPDATE hallazgo SET estado = 'cerrado', cerrado_en = now(), actualizado_en = now() "
                 "WHERE id = %s AND creado_en = %s", (co["hallazgo_id"], co["hallazgo_creado_en"]))
    # Las demás sugerencias de ese reporte o hallazgo ya no aplican
    conn.execute(
        "UPDATE coincidencia SET estado = 'rechazada', decidido_por = %s, decidido_en = now(), "
        "motivo_rechazo = 'Objeto entregado por otra coincidencia' WHERE sede_id = %s AND estado = 'sugerida' "
        "AND (reporte_id = %s OR hallazgo_id = %s)",
        (u.id, u.sede_id, co["reporte_id"], co["hallazgo_id"]),
    )
    publicar_evento(conn, "entrega", entrega["id"], u.sede_id, "entrega.registrada", {
        "id": str(entrega["id"]), "coincidencia_id": str(datos.coincidencia_id),
        "reporte_id": str(co["reporte_id"]), "hallazgo_id": str(co["hallazgo_id"]),
        "creado_en": entrega["creado_en"].isoformat(),
    })
    auditar(conn, u.id, "crear", "entrega", entrega["id"], u.sede_id, ip=ip_cliente(request))
    return {"entregado": True, "entrega_id": entrega["id"], "estado_caso": "cerrado"}
