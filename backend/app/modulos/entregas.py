"""Entrega al dueño (HU-08, HU-09): carné + pregunta de control, acta y cierre del caso.

POST /entregas                                registrar (el número del acta lo pone el sistema)
GET  /entregas                                registro de entregas de la sede (sin datos del dueño)
GET  /entregas/{id}/acta                      datos del acta para imprimir (lectura auditada)
POST /entregas/{id}/acta-firmada              foto del acta firmada (reemplaza la anterior)
GET  /entregas/{id}/acta-firmada/{tamano}     verla (solo el admin de la sede)

Número del acta: ACTA-<código de sede>-<año>-<consecutivo de 5 dígitos>. Sale de la tabla
consecutivo_acta en la misma transacción de la entrega: dos entregas a la vez nunca reciben
el mismo número, y si la entrega falla el número no se gasta.

Intentos fallidos (ADR-019): cada uno queda en intento_entrega con su motivo. Al tercero, la
coincidencia se rechaza sola y el objeto vuelve a custodia para que el matcher siga buscando.
No se marca a la persona: quien falla puede ser el dueño real que olvidó un detalle.
"""

from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Query, Request, Response, UploadFile
from psycopg import Connection
from pydantic import BaseModel, Field

from app import fotos
from app.db import get_conn
from app.errores import ErrorApp, conflicto, no_encontrado
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, decodificar_cursor, ip_cliente, paginar, solo_admin

router = APIRouter(prefix="/entregas", tags=["entregas"])


class Entrega(BaseModel):
    coincidencia_id: UUID
    verificacion_ok: bool = Field(description="El reclamante mostró carné y respondió bien la pregunta de control")
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
    numero_acta = siguiente_acta(conn, u.sede_id)
    entrega = conn.execute(
        "INSERT INTO entrega (sede_id, coincidencia_id, estudiante_id, verificacion_ok, numero_acta, observaciones, "
        "registrado_por) VALUES (%s, %s, %s, true, %s, %s, %s) RETURNING id, creado_en",
        (u.sede_id, datos.coincidencia_id, co["estudiante_id"], numero_acta, datos.observaciones, u.id),
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
    return {"entregado": True, "entrega_id": entrega["id"], "numero_acta": numero_acta, "estado_caso": "entregado"}


def siguiente_acta(conn: Connection, sede_id: int) -> str:
    """Siguiente número de acta de la sede en el año (Bogotá). La fila queda bloqueada hasta el commit."""
    fila = conn.execute(
        "WITH a AS (SELECT extract(year FROM now() AT TIME ZONE 'America/Bogota')::smallint AS anio) "
        "INSERT INTO consecutivo_acta (sede_id, anio, ultimo) SELECT %(sede)s, a.anio, 1 FROM a "
        "ON CONFLICT (sede_id, anio) DO UPDATE SET ultimo = consecutivo_acta.ultimo + 1 "
        "RETURNING anio, ultimo, (SELECT codigo FROM sede WHERE id = %(sede)s) AS codigo",
        {"sede": sede_id},
    ).fetchone()
    return f"ACTA-{fila['codigo']}-{fila['anio']}-{fila['ultimo']:05d}"


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


# ------------------------------------------------------------------ registro y acta
@router.get("")
def listar(firma: Literal["pendiente", "firmada"] | None = None, cursor: str | None = None,
           limite: int = Query(20, ge=1, le=100), u: Usuario = Depends(solo_admin),
           conn: Connection = Depends(get_conn)) -> dict:
    """Registro de entregas de la sede, de la más reciente a la más antigua. Sin datos del dueño."""
    filtros, params = ["e.sede_id = %s"], [u.sede_id]
    if firma:
        filtros.append("e.acta_clave IS " + ("NULL" if firma == "pendiente" else "NOT NULL"))
    if cursor:
        c_fecha, c_id = decodificar_cursor(cursor)
        filtros.append("(e.creado_en, e.id) < (%s, %s)")
        params += [c_fecha, c_id]
    filas = conn.execute(
        "SELECT e.id, e.creado_en, e.numero_acta, e.acta_clave IS NOT NULL AS firmada, e.acta_subida_en, "
        "c.nombre AS categoria, h.descripcion_publica, us.nombre AS entregado_por FROM entrega e "
        "JOIN coincidencia co ON co.id = e.coincidencia_id AND co.sede_id = e.sede_id "
        "JOIN hallazgo h ON h.id = co.hallazgo_id AND h.creado_en = co.hallazgo_creado_en AND h.sede_id = co.sede_id "
        "JOIN categoria c ON c.id = h.categoria_id JOIN usuario us ON us.id = e.registrado_por "
        "WHERE " + " AND ".join(filtros) + " ORDER BY e.creado_en DESC, e.id DESC LIMIT %s",
        [*params, limite + 1],
    ).fetchall()
    items, siguiente = paginar(filas, limite)
    pendientes = conn.execute("SELECT count(*) AS n FROM entrega WHERE sede_id = %s AND acta_clave IS NULL",
                              (u.sede_id,)).fetchone()["n"]
    return {"items": items, "siguiente": siguiente, "sin_firma": pendientes}


def _entrega_de_sede(conn: Connection, entrega_id: UUID, sede_id: int) -> dict:
    fila = conn.execute("SELECT id, numero_acta, acta_clave FROM entrega WHERE id = %s AND sede_id = %s",
                        (entrega_id, sede_id)).fetchone()
    if not fila:
        raise no_encontrado("La entrega")
    return fila


@router.get("/{entrega_id}/acta")
def acta(entrega_id: UUID, request: Request, u: Usuario = Depends(solo_admin),
         conn: Connection = Depends(get_conn)) -> dict:
    """Todo lo que va impreso en el acta. Tiene datos del dueño: la lectura queda auditada."""
    fila = conn.execute(
        "SELECT e.id, e.numero_acta, e.creado_en, e.metodo_verificacion, e.observaciones, "
        "e.acta_clave IS NOT NULL AS firmada, e.acta_subida_en, sub.nombre AS acta_subida_por, "
        "s.nombre AS sede, s.ciudad, s.direccion, us.nombre AS entregado_por, us.email AS correo_admin, "
        "es.nombres, es.apellidos, es.tipo_documento, es.numero_documento, es.programa, "
        "es.anonimizado_en IS NOT NULL AS anonimizado, "
        "c.nombre AS categoria, h.descripcion, h.fecha_hallazgo, h.ubicacion_bodega, zh.nombre AS zona_hallazgo, "
        "r.fecha_perdida, sr.nombre AS sede_reporte, co.creado_en AS sugerida_en, co.decidido_en AS verificada_en "
        "FROM entrega e JOIN sede s ON s.id = e.sede_id JOIN usuario us ON us.id = e.registrado_por "
        "LEFT JOIN usuario sub ON sub.id = e.acta_subida_por JOIN estudiante es ON es.id = e.estudiante_id "
        "JOIN coincidencia co ON co.id = e.coincidencia_id AND co.sede_id = e.sede_id "
        "JOIN hallazgo h ON h.id = co.hallazgo_id AND h.creado_en = co.hallazgo_creado_en AND h.sede_id = co.sede_id "
        "JOIN categoria c ON c.id = h.categoria_id LEFT JOIN zona zh ON zh.id = h.zona_id "
        "JOIN reporte_perdida r ON r.id = co.reporte_id AND r.creado_en = co.reporte_creado_en "
        "AND r.sede_id = co.reporte_sede_id JOIN sede sr ON sr.id = r.sede_id "
        "WHERE e.id = %s AND e.sede_id = %s",
        (entrega_id, u.sede_id),
    ).fetchone()
    if not fila:
        raise no_encontrado("La entrega")
    auditar(conn, u.id, "leer", "entrega", entrega_id, u.sede_id, motivo="acta de entrega", ip=ip_cliente(request))
    return fila


@router.post("/{entrega_id}/acta-firmada", status_code=201)
def subir_acta(entrega_id: UUID, request: Request,
               archivo: Annotated[UploadFile, File(description="Foto del acta firmada: JPG, PNG, WebP o HEIC")],
               u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> dict:
    e = _entrega_de_sede(conn, entrega_id, u.sede_id)
    imagen = fotos.procesar(archivo.file.read(fotos.MAX_BYTES + 1))
    clave = f"actas/{entrega_id}/{uuid4().hex}"
    fotos.guardar(clave, imagen)
    fila = conn.execute(
        "UPDATE entrega SET acta_clave = %s, acta_subida_en = now(), acta_subida_por = %s "
        "WHERE id = %s AND sede_id = %s RETURNING acta_subida_en", (clave, u.id, entrega_id, u.sede_id)).fetchone()
    if e["acta_clave"]:
        fotos.borrar(e["acta_clave"])  # la nueva reemplaza a la anterior
    auditar(conn, u.id, "actualizar", "entrega", entrega_id, u.sede_id, ip=ip_cliente(request),
            detalle={"acta_firmada": "reemplazada" if e["acta_clave"] else "subida"})
    return {"firmada": True, "acta_subida_en": fila["acta_subida_en"]}


@router.get("/{entrega_id}/acta-firmada/{tamano}")
def ver_acta(entrega_id: UUID, tamano: Literal["grande", "mini"], request: Request,
             u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> Response:
    e = _entrega_de_sede(conn, entrega_id, u.sede_id)
    if not e["acta_clave"]:
        raise no_encontrado("El acta firmada")
    if tamano == "grande":
        auditar(conn, u.id, "leer", "entrega", entrega_id, u.sede_id, motivo="acta firmada", ip=ip_cliente(request))
    return Response(fotos.leer(e["acta_clave"], tamano), media_type="image/webp",
                    headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})
