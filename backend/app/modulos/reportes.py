"""Reportes de pérdida (HU-02). Solo admins; cada admin ve y crea en su sede."""

from datetime import date, time
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from psycopg import Connection
from pydantic import BaseModel, Field, field_validator

from app import idempotencia
from app.cache import get_redis
from app.db import get_conn
from app.errores import ErrorApp, conflicto, no_encontrado
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, decodificar_cursor, ip_cliente, paginar, solo_admin

router = APIRouter(prefix="/reportes", tags=["reportes"])


class ReporteNuevo(BaseModel):
    estudiante_id: UUID
    categoria_id: int = Field(ge=1)
    zona_id: int | None = None
    descripcion: str = Field(min_length=5, max_length=1000, description="Uso interno; puede mencionar al dueño")
    descripcion_publica: str = Field(min_length=5, max_length=300, description="Sin datos personales")
    detalle_control: str | None = Field(default=None, max_length=300,
                                        description="Detalle oculto para la pregunta de control")
    fecha_perdida: date
    hora_aprox: time | None = None

    @field_validator("fecha_perdida")
    @classmethod
    def _no_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("la fecha de pérdida no puede estar en el futuro")
        return v


def validar_catalogos(conn: Connection, sede_id: int, categoria_id: int, zona_id: int | None) -> None:
    if not conn.execute("SELECT 1 FROM categoria WHERE id = %s", (categoria_id,)).fetchone():
        raise ErrorApp(422, "validacion", "La categoría no existe")
    if zona_id is not None and not conn.execute(
        "SELECT 1 FROM zona WHERE id = %s AND sede_id = %s", (zona_id, sede_id)
    ).fetchone():
        raise ErrorApp(422, "validacion", "La zona no existe en tu sede")


@router.post("", status_code=201)
def crear(datos: ReporteNuevo, request: Request, idempotency_key: str | None = Header(default=None),
          u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn), r=Depends(get_redis)) -> dict:
    def _crear() -> dict:
        est = conn.execute("SELECT anonimizado_en FROM estudiante WHERE id = %s", (datos.estudiante_id,)).fetchone()
        if not est:
            raise no_encontrado("El estudiante")
        if not conn.execute(
            "SELECT 1 FROM consentimiento WHERE estudiante_id = %s AND revocado_en IS NULL "
            "AND 'gestion_objeto' = ANY(finalidades)", (datos.estudiante_id,)
        ).fetchone():
            raise conflicto("Falta el consentimiento del estudiante para gestionar su objeto (Ley 1581)")
        validar_catalogos(conn, u.sede_id, datos.categoria_id, datos.zona_id)
        fila = conn.execute(
            "INSERT INTO reporte_perdida (sede_id, estudiante_id, categoria_id, zona_id, descripcion, "
            "descripcion_publica, detalle_control, fecha_perdida, hora_aprox, registrado_por) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, sede_id, creado_en, estado",
            (u.sede_id, datos.estudiante_id, datos.categoria_id, datos.zona_id, datos.descripcion,
             datos.descripcion_publica, datos.detalle_control, datos.fecha_perdida, datos.hora_aprox, u.id),
        ).fetchone()
        publicar_evento(conn, "reporte_perdida", fila["id"], u.sede_id, "reporte.creado", {
            "id": str(fila["id"]), "creado_en": fila["creado_en"].isoformat(), "categoria_id": datos.categoria_id,
            "zona_id": datos.zona_id, "fecha": datos.fecha_perdida.isoformat(),
        })
        auditar(conn, u.id, "crear", "reporte_perdida", fila["id"], u.sede_id, ip=ip_cliente(request))
        return {"id": str(fila["id"]), "creado_en": fila["creado_en"].isoformat(), "estado": fila["estado"]}

    respuesta, _ = idempotencia.ejecutar(r, u.id, idempotency_key, _crear)
    return respuesta


@router.get("")
def listar(estado: str | None = None, cursor: str | None = None, limite: int = Query(20, ge=1, le=100),
           u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> dict:
    """Bandeja del admin (índice reporte_sede_estado_idx). Sin datos del estudiante."""
    filtros, params = ["r.sede_id = %s"], [u.sede_id]
    if estado:
        filtros.append("r.estado = %s::estado_reporte")
        params.append(estado)
    if cursor:
        c_fecha, c_id = decodificar_cursor(cursor)
        filtros.append("(r.creado_en, r.id) < (%s, %s)")
        params += [c_fecha, c_id]
    filas = conn.execute(
        "SELECT r.id, r.creado_en, r.estado, c.nombre AS categoria, z.nombre AS zona, r.descripcion_publica, "
        "r.fecha_perdida FROM reporte_perdida r JOIN categoria c ON c.id = r.categoria_id "
        "LEFT JOIN zona z ON z.id = r.zona_id WHERE " + " AND ".join(filtros) +
        " ORDER BY r.creado_en DESC, r.id DESC LIMIT %s",
        [*params, limite + 1],
    ).fetchall()
    items, siguiente = paginar(filas, limite)
    return {"items": items, "siguiente": siguiente}


@router.get("/{reporte_id}")
def detalle(reporte_id: UUID, request: Request, u: Usuario = Depends(solo_admin),
            conn: Connection = Depends(get_conn)) -> dict:
    """Incluye datos del dueño y el detalle de control: la lectura queda auditada."""
    fila = conn.execute(
        "SELECT r.*, c.nombre AS categoria, z.nombre AS zona, e.nombres, e.apellidos, e.tipo_documento, "
        "e.numero_documento, e.correo_institucional, e.telefono FROM reporte_perdida r "
        "JOIN categoria c ON c.id = r.categoria_id LEFT JOIN zona z ON z.id = r.zona_id "
        "JOIN estudiante e ON e.id = r.estudiante_id WHERE r.id = %s AND r.sede_id = %s",
        (reporte_id, u.sede_id),
    ).fetchone()
    if not fila:
        raise no_encontrado("El reporte")
    auditar(conn, u.id, "leer", "reporte_perdida", reporte_id, u.sede_id, motivo="detalle del reporte",
            ip=ip_cliente(request))
    return fila
