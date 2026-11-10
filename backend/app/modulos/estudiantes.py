"""Estudiantes (dueños), consentimiento y derecho de supresión (Ley 1581).

Toda lectura de datos personales queda en auditoría con el motivo (HU-14).
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from psycopg import Connection, errors
from pydantic import BaseModel, EmailStr, Field

from app.config import get_settings
from app.db import get_conn
from app.errores import conflicto, no_encontrado
from app.registro import auditar, publicar_evento
from app.seguridad import Usuario, ip_cliente, solo_admin

router = APIRouter(tags=["estudiantes"])

COLUMNAS = ("id, tipo_documento, numero_documento, nombres, apellidos, correo_institucional, telefono, "
            "programa, anonimizado_en, creado_en")


class EstudianteNuevo(BaseModel):
    tipo_documento: Literal["CC", "TI", "CE", "PA", "PPT"]
    numero_documento: str = Field(pattern=r"^[A-Za-z0-9]{4,20}$")
    nombres: str = Field(min_length=1, max_length=80)
    apellidos: str = Field(min_length=1, max_length=80)
    correo_institucional: EmailStr | None = None
    telefono: str | None = Field(default=None, pattern=r"^\+?[0-9 ]{7,15}$")
    programa: str | None = Field(default=None, max_length=120)


class Consentimiento(BaseModel):
    estudiante_id: UUID
    finalidades: list[Literal["gestion_objeto", "notificacion_correo"]] = Field(min_length=1)
    canal: Literal["presencial", "correo"] = "presencial"


@router.post("/estudiantes", status_code=201)
def crear_estudiante(datos: EstudianteNuevo, request: Request, u: Usuario = Depends(solo_admin),
                     conn: Connection = Depends(get_conn)) -> dict:
    try:
        with conn.transaction():  # savepoint: un duplicado no invalida la transacción
            fila = conn.execute(
                f"INSERT INTO estudiante (tipo_documento, numero_documento, nombres, apellidos, "
                f"correo_institucional, telefono, programa) VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING {COLUMNAS}",
                (datos.tipo_documento, datos.numero_documento, datos.nombres, datos.apellidos,
                 datos.correo_institucional, datos.telefono, datos.programa),
            ).fetchone()
    except errors.UniqueViolation as exc:
        raise conflicto("Ya existe un estudiante con ese documento; búscalo en lugar de crearlo") from exc
    auditar(conn, u.id, "crear", "estudiante", fila["id"], u.sede_id, ip=ip_cliente(request))
    return fila


@router.get("/estudiantes")
def buscar_estudiante(request: Request, tipo_documento: str = Query(...), numero_documento: str = Query(...),
                      motivo: str = Query("registro de reporte", max_length=120),
                      u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> dict:
    fila = conn.execute(
        f"SELECT {COLUMNAS} FROM estudiante WHERE tipo_documento = %s AND numero_documento = %s",
        (tipo_documento, numero_documento),
    ).fetchone()
    if not fila:
        raise no_encontrado("El estudiante")
    auditar(conn, u.id, "leer", "estudiante", fila["id"], u.sede_id, motivo=motivo, ip=ip_cliente(request))
    vigente = conn.execute(
        "SELECT version_aviso, finalidades, otorgado_en FROM consentimiento "
        "WHERE estudiante_id = %s AND revocado_en IS NULL ORDER BY otorgado_en DESC LIMIT 1",
        (fila["id"],),
    ).fetchone()
    return {**fila, "consentimiento_vigente": vigente}


@router.post("/consentimientos", status_code=201)
def registrar_consentimiento(datos: Consentimiento, request: Request, u: Usuario = Depends(solo_admin),
                             conn: Connection = Depends(get_conn)) -> dict:
    existe = conn.execute("SELECT anonimizado_en FROM estudiante WHERE id = %s", (datos.estudiante_id,)).fetchone()
    if not existe:
        raise no_encontrado("El estudiante")
    if existe["anonimizado_en"]:
        raise conflicto("El estudiante pidió la supresión de sus datos")
    fila = conn.execute(
        "INSERT INTO consentimiento (estudiante_id, version_aviso, finalidades, canal, registrado_por) "
        "VALUES (%s, %s, %s, %s, %s) RETURNING id, version_aviso, finalidades, otorgado_en",
        (datos.estudiante_id, get_settings().version_aviso_privacidad, datos.finalidades, datos.canal, u.id),
    ).fetchone()
    auditar(conn, u.id, "crear", "consentimiento", fila["id"], u.sede_id, ip=ip_cliente(request))
    return fila


@router.post("/estudiantes/{estudiante_id}/anonimizar")
def anonimizar(estudiante_id: UUID, request: Request, u: Usuario = Depends(solo_admin),
               conn: Connection = Depends(get_conn)) -> dict:
    """Derecho de supresión (HU-15): borra los datos personales y conserva lo estadístico."""
    fila = conn.execute(
        "UPDATE estudiante SET tipo_documento = 'CC', numero_documento = 'ANON-' || left(id::text, 8), "
        "nombres = 'Anonimizado', apellidos = 'Anonimizado', correo_institucional = NULL, telefono = NULL, "
        "programa = NULL, anonimizado_en = now(), actualizado_en = now() "
        "WHERE id = %s AND anonimizado_en IS NULL RETURNING id",
        (estudiante_id,),
    ).fetchone()
    if not fila:
        raise no_encontrado("El estudiante (o ya estaba anonimizado)")
    conn.execute("UPDATE consentimiento SET revocado_en = now() WHERE estudiante_id = %s AND revocado_en IS NULL",
                 (estudiante_id,))
    # Las descripciones internas pueden mencionar al dueño: se reemplazan por la pública
    conn.execute("UPDATE reporte_perdida SET descripcion = descripcion_publica, detalle_control = NULL "
                 "WHERE estudiante_id = %s", (estudiante_id,))
    auditar(conn, u.id, "anonimizar", "estudiante", estudiante_id, u.sede_id, ip=ip_cliente(request))
    publicar_evento(conn, "estudiante", estudiante_id, None, "estudiante.anonimizado", {"id": str(estudiante_id)})
    return {"id": estudiante_id, "anonimizado": True}
