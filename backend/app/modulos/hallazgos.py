"""Hallazgos (HU-03). La custodia vence a los DIAS_CUSTODIA días (HU-16)."""

from datetime import date, time, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request
from psycopg import Connection
from pydantic import BaseModel, Field, field_validator

from app import idempotencia
from app.cache import get_redis
from app.config import get_settings
from app.db import get_conn
from app.errores import no_encontrado
from app.modulos.reportes import validar_catalogos
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, decodificar_cursor, ip_cliente, paginar, solo_admin

router = APIRouter(prefix="/hallazgos", tags=["hallazgos"])


class HallazgoNuevo(BaseModel):
    categoria_id: int = Field(ge=1)
    zona_id: int | None = None
    descripcion: str = Field(min_length=5, max_length=1000)
    descripcion_publica: str = Field(min_length=5, max_length=300)
    fecha_hallazgo: date
    hora_aprox: time | None = None
    encontrado_por: str | None = Field(default=None, max_length=120, description="Opcional (dato personal)")
    ubicacion_bodega: str | None = Field(default=None, max_length=60)

    @field_validator("fecha_hallazgo")
    @classmethod
    def _no_futura(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("la fecha del hallazgo no puede estar en el futuro")
        return v


@router.post("", status_code=201)
def crear(datos: HallazgoNuevo, request: Request, idempotency_key: str | None = Header(default=None),
          u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn), r=Depends(get_redis)) -> dict:
    def _crear() -> dict:
        validar_catalogos(conn, u.sede_id, datos.categoria_id, datos.zona_id)
        vence = date.today() + timedelta(days=get_settings().dias_custodia)
        fila = conn.execute(
            "INSERT INTO hallazgo (sede_id, categoria_id, zona_id, descripcion, descripcion_publica, "
            "fecha_hallazgo, hora_aprox, encontrado_por, ubicacion_bodega, vence_en, registrado_por) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, creado_en, estado, vence_en",
            (u.sede_id, datos.categoria_id, datos.zona_id, datos.descripcion, datos.descripcion_publica,
             datos.fecha_hallazgo, datos.hora_aprox, datos.encontrado_por, datos.ubicacion_bodega, vence, u.id),
        ).fetchone()
        publicar_evento(conn, "hallazgo", fila["id"], u.sede_id, "hallazgo.creado", {
            "id": str(fila["id"]), "creado_en": fila["creado_en"].isoformat(), "categoria_id": datos.categoria_id,
            "zona_id": datos.zona_id, "fecha": datos.fecha_hallazgo.isoformat(),
        })
        auditar(conn, u.id, "crear", "hallazgo", fila["id"], u.sede_id, ip=ip_cliente(request))
        return {"id": str(fila["id"]), "creado_en": fila["creado_en"].isoformat(), "estado": fila["estado"],
                "vence_en": fila["vence_en"].isoformat()}

    respuesta, _ = idempotencia.ejecutar(r, u.id, idempotency_key, _crear)
    return respuesta


@router.get("")
def listar(estado: str | None = None, cursor: str | None = None, limite: int = Query(20, ge=1, le=100),
           u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> dict:
    filtros, params = ["h.sede_id = %s"], [u.sede_id]
    if estado:
        filtros.append("h.estado = %s::estado_hallazgo")
        params.append(estado)
    if cursor:
        c_fecha, c_id = decodificar_cursor(cursor)
        filtros.append("(h.creado_en, h.id) < (%s, %s)")
        params += [c_fecha, c_id]
    filas = conn.execute(
        "SELECT h.id, h.creado_en, h.estado, c.nombre AS categoria, z.nombre AS zona, h.descripcion_publica, "
        "h.fecha_hallazgo, h.ubicacion_bodega, h.vence_en FROM hallazgo h JOIN categoria c ON c.id = h.categoria_id "
        "LEFT JOIN zona z ON z.id = h.zona_id WHERE " + " AND ".join(filtros) +
        " ORDER BY h.creado_en DESC, h.id DESC LIMIT %s",
        [*params, limite + 1],
    ).fetchall()
    items, siguiente = paginar(filas, limite)
    return {"items": items, "siguiente": siguiente}


@router.get("/{hallazgo_id}")
def detalle(hallazgo_id: UUID, request: Request, u: Usuario = Depends(solo_admin),
            conn: Connection = Depends(get_conn)) -> dict:
    fila = conn.execute(
        "SELECT h.*, c.nombre AS categoria, z.nombre AS zona FROM hallazgo h JOIN categoria c ON c.id = h.categoria_id "
        "LEFT JOIN zona z ON z.id = h.zona_id WHERE h.id = %s AND h.sede_id = %s",
        (hallazgo_id, u.sede_id),
    ).fetchone()
    if not fila:
        raise no_encontrado("El hallazgo")
    if fila["encontrado_por"]:
        auditar(conn, u.id, "leer", "hallazgo", hallazgo_id, u.sede_id, motivo="detalle del hallazgo",
                ip=ip_cliente(request))
    return fila
