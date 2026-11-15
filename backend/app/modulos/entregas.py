"""Entrega al dueño (HU-08, HU-09): carné + pregunta de control, acta y cierre del caso.

Intentos fallidos (ADR-019): cada uno queda en intento_entrega con su motivo. Al tercero, la
coincidencia se rechaza sola y el objeto vuelve a custodia para que el matcher siga buscando.
No se marca a la persona: quien falla puede ser el dueño real que olvidó un detalle.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from psycopg import Connection
from pydantic import BaseModel, Field

from app.db import get_conn
from app.errores import ErrorApp, conflicto, no_encontrado
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, ip_cliente, solo_admin

router = APIRouter(prefix="/entregas", tags=["entregas"])


class Entrega(BaseModel):
    coincidencia_id: UUID
    verificacion_ok: bool = Field(description="El reclamante mostró carné y respondió bien la pregunta de control")
    numero_acta: str | None = Field(default=None, min_length=3, max_length=40, description="Obligatorio si se entrega")
    motivo_fallo: Literal["documento", "pregunta_control", "otro"] | None = Field(
        default=None, description="Obligatorio si la verificación falló")
    observaciones: str | None = Field(default=None, max_length=500)


MAX_INTENTOS = 3


@router.post("")
def registrar(datos: Entrega, request: Request, u: Usuario = Depends(solo_admin),
              conn: Connection = Depends(get_conn)) -> dict:
    co = conn.execute(
        "SELECT co.*, r.estudiante_id FROM coincidencia co JOIN reporte_perdida r "
        "ON (r.id, r.creado_en, r.sede_id) = (co.reporte_id, co.reporte_creado_en, co.reporte_sede_id) "
        "WHERE co.id = %s AND co.sede_id = %s FOR UPDATE OF co",
        (datos.coincidencia_id, u.sede_id),
    ).fetchone()
    if not co:
        raise no_encontrado("La coincidencia")
    if co["estado"] != "verificada":
        raise conflicto("Solo se entrega un objeto con la coincidencia verificada", {"estado": co["estado"]})

    if not datos.verificacion_ok:
        return _intento_fallido(conn, co, datos, u, request)
    if not datos.numero_acta:
        raise ErrorApp(422, "validacion", "Falta el número del acta",
                       [{"campo": "numero_acta", "error": "Field required"}])

    entrega = conn.execute(
        "INSERT INTO entrega (sede_id, coincidencia_id, estudiante_id, verificacion_ok, numero_acta, observaciones, "
        "registrado_por) VALUES (%s, %s, %s, true, %s, %s, %s) RETURNING id, creado_en",
        (u.sede_id, datos.coincidencia_id, co["estudiante_id"], datos.numero_acta, datos.observaciones, u.id),
    ).fetchone()
    conn.execute("UPDATE coincidencia SET estado = 'entregada' WHERE id = %s AND sede_id = %s",
                 (datos.coincidencia_id, u.sede_id))
    conn.execute("UPDATE reporte_perdida SET estado = 'entregado', cerrado_en = now(), actualizado_en = now() "
                 "WHERE id = %s AND creado_en = %s", (co["reporte_id"], co["reporte_creado_en"]))
    conn.execute("UPDATE hallazgo SET estado = 'entregado', cerrado_en = now(), actualizado_en = now() "
                 "WHERE id = %s AND creado_en = %s", (co["hallazgo_id"], co["hallazgo_creado_en"]))
    # Las demás sugerencias de ese reporte o hallazgo ya no aplican
    conn.execute(
        "UPDATE coincidencia SET estado = 'rechazada', decidido_por = %s, decidido_en = now(), "
        "motivo_rechazo = 'Objeto entregado por otra coincidencia' WHERE estado = 'sugerida' "
        "AND (reporte_id = %s OR hallazgo_id = %s)",   # en cualquier sede de la ciudad (ADR-020)
        (u.id, co["reporte_id"], co["hallazgo_id"]),
    )
    publicar_evento(conn, "entrega", entrega["id"], u.sede_id, "entrega.registrada", {
        "id": str(entrega["id"]), "coincidencia_id": str(datos.coincidencia_id),
        "reporte_id": str(co["reporte_id"]), "hallazgo_id": str(co["hallazgo_id"]),
        "creado_en": entrega["creado_en"].isoformat(),
    })
    auditar(conn, u.id, "crear", "entrega", entrega["id"], u.sede_id, ip=ip_cliente(request))
    return {"entregado": True, "entrega_id": entrega["id"], "estado_caso": "entregado"}


def _intento_fallido(conn: Connection, co: dict, datos: Entrega, u: Usuario, request: Request) -> dict:
    if datos.motivo_fallo is None:
        raise ErrorApp(422, "validacion", "Indica por qué no pasó la verificación",
                       [{"campo": "motivo_fallo", "error": "Field required"}])
    conn.execute("INSERT INTO intento_entrega (sede_id, coincidencia_id, motivo, observaciones, registrado_por) "
                 "VALUES (%s, %s, %s, %s, %s)", (u.sede_id, co["id"], datos.motivo_fallo, datos.observaciones, u.id))
    intentos = conn.execute("SELECT count(*) AS n FROM intento_entrega WHERE coincidencia_id = %s",
                            (co["id"],)).fetchone()["n"]
    auditar(conn, u.id, "actualizar", "entrega", co["id"], u.sede_id, ip=ip_cliente(request),
            detalle={"resultado": "verificacion_fallida", "motivo": datos.motivo_fallo, "intento": intentos})
    if intentos < MAX_INTENTOS:
        return {"entregado": False, "intentos": intentos, "restantes": MAX_INTENTOS - intentos,
                "liberada": False,
                "motivo": f"No pasó la verificación (intento {intentos} de {MAX_INTENTOS}). "
                          "El objeto sigue en custodia."}

    # Tercer fallo: la coincidencia se descarta y el objeto vuelve a estar disponible para otro dueño
    conn.execute("UPDATE coincidencia SET estado = 'rechazada', decidido_por = %s, decidido_en = now(), "
                 "motivo_rechazo = %s WHERE id = %s AND sede_id = %s",
                 (u.id, f"Verificación fallida {MAX_INTENTOS} veces", co["id"], u.sede_id))
    for tabla, columna, ident, creado in (("reporte_perdida", "reporte_id", co["reporte_id"], co["reporte_creado_en"]),
                                          ("hallazgo", "hallazgo_id", co["hallazgo_id"], co["hallazgo_creado_en"])):
        # Vuelve a 'publicado' solo si no queda otra coincidencia verificada sobre el mismo objeto
        conn.execute(
            f"UPDATE {tabla} SET estado = 'publicado', actualizado_en = now() WHERE id = %s AND creado_en = %s "  # noqa: S608
            f"AND estado = 'en_coincidencia' AND NOT EXISTS (SELECT 1 FROM coincidencia c WHERE c.{columna} = %s "
            f"AND c.estado = 'verificada' AND c.id <> %s)", (ident, creado, ident, co["id"]))
    publicar_evento(conn, "coincidencia", co["id"], u.sede_id, "coincidencia.rechazada",
                    {"id": str(co["id"]), "puntaje": float(co["puntaje"])})
    return {"entregado": False, "intentos": intentos, "restantes": 0, "liberada": True,
            "motivo": f"No pasó la verificación {MAX_INTENTOS} veces: la coincidencia se descartó y el objeto "
                      "volvió a custodia para seguir buscando a su dueño."}
