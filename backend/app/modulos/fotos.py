"""Fotos de reportes y hallazgos (ADR-018).

POST   /reportes/{id}/fotos · /hallazgos/{id}/fotos   subir (admin de la sede, máx. 3)
GET    /fotos/{foto_id}/{tamano}                       ver (admin de la sede)
DELETE /fotos/{foto_id}                                borrar (admin de la sede)
GET    /publico/fotos/{foto_id}/{tamano}               solo fotos de reportes de pérdida publicados
                                                       y nunca de documentos (vista_publica_fotos)
"""

import logging
import threading
import time
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from psycopg import Connection

from app import fotos
from app.db import get_conn, pool
from app.errores import conflicto, no_encontrado
from app.modulos.publico import limite_publico
from app.registro import auditar
from app.seguridad import Usuario, ip_cliente, solo_admin

log = logging.getLogger("fotos")
router = APIRouter(tags=["fotos"])

TABLAS = {"reportes": ("reporte_perdida", "perdido"), "hallazgos": ("hallazgo", "hallado")}
ESTADOS_ABIERTOS = ("registrado", "publicado", "en_coincidencia")
Tamano = Literal["grande", "mini"]


def fotos_de(conn: Connection, objeto_tipo: str, objeto_id) -> list[dict]:
    return conn.execute("SELECT id, orden, ancho, alto FROM foto_objeto WHERE objeto_tipo = %s AND objeto_id = %s "
                        "ORDER BY orden", (objeto_tipo, objeto_id)).fetchall()


@router.post("/{coleccion}/{objeto_id}/fotos", status_code=201)
def subir(coleccion: Literal["reportes", "hallazgos"], objeto_id: UUID, request: Request,
          archivo: Annotated[UploadFile, File(description="JPG, PNG, WebP o HEIC, máx. 8 MB")],
          u: Usuario = Depends(solo_admin), conn: Connection = Depends(get_conn)) -> dict:
    tabla, tipo = TABLAS[coleccion]
    obj = conn.execute(f"SELECT estado::text FROM {tabla} WHERE id = %s AND sede_id = %s",  # noqa: S608 - fija
                       (objeto_id, u.sede_id)).fetchone()
    if not obj:
        raise no_encontrado("El objeto")
    if obj["estado"] not in ESTADOS_ABIERTOS:
        raise conflicto("El caso ya está cerrado: no se le pueden agregar fotos")
    actuales = fotos_de(conn, tipo, objeto_id)
    if len(actuales) >= fotos.MAX_FOTOS:
        raise conflicto(f"Ya tiene {fotos.MAX_FOTOS} fotos. Borra una para subir otra.")

    datos = archivo.file.read(fotos.MAX_BYTES + 1)  # ruta síncrona: FastAPI la corre en un hilo
    foto = fotos.procesar(datos)
    if any(conn.execute("SELECT 1 FROM foto_objeto WHERE objeto_tipo = %s AND objeto_id = %s AND sha256 = %s",
                        (tipo, objeto_id, foto.sha256)).fetchall()):
        raise conflicto("Esa misma foto ya está cargada en este objeto")
    orden = min({1, 2, 3} - {f["orden"] for f in actuales})
    clave = f"{tipo}/{objeto_id}/{uuid4().hex}"
    fotos.guardar(clave, foto)
    fila = conn.execute(
        "INSERT INTO foto_objeto (sede_id, objeto_tipo, objeto_id, orden, clave, ancho, alto, bytes, sha256, "
        "subido_por) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id, orden, ancho, alto",
        (u.sede_id, tipo, objeto_id, orden, clave, foto.ancho, foto.alto, len(foto.archivos["grande"]),
         foto.sha256, u.id),
    ).fetchone()
    auditar(conn, u.id, "crear", "foto_objeto", fila["id"], u.sede_id, ip=ip_cliente(request),
            detalle={"objeto": str(objeto_id), "tipo": tipo})
    return fila


def _foto_de_sede(conn: Connection, foto_id: UUID, sede_id: int) -> dict:
    fila = conn.execute("SELECT id, clave, objeto_tipo::text AS objeto_tipo, objeto_id FROM foto_objeto "
                        "WHERE id = %s AND sede_id = %s", (foto_id, sede_id)).fetchone()
    if not fila:
        raise no_encontrado("La foto")
    return fila


def _imagen(datos: bytes, publica: bool) -> Response:
    # Las claves no se reutilizan: la caché del navegador puede ser larga sin riesgo de ver otra foto
    cache = "public, max-age=86400" if publica else "private, max-age=3600"
    return Response(datos, media_type="image/webp",
                    headers={"Cache-Control": cache, "X-Content-Type-Options": "nosniff"})


@router.get("/fotos/{foto_id}/{tamano}")
def ver(foto_id: UUID, tamano: Tamano, u: Usuario = Depends(solo_admin),
        conn: Connection = Depends(get_conn)) -> Response:
    # La sede de custodia también ve las fotos del reporte (de otra sede) con el que tiene una coincidencia
    fila = conn.execute(
        "SELECT f.clave FROM foto_objeto f WHERE f.id = %(id)s AND (f.sede_id = %(sede)s OR (f.objeto_tipo = 'perdido' "
        "AND EXISTS (SELECT 1 FROM coincidencia co WHERE co.reporte_id = f.objeto_id AND co.sede_id = %(sede)s)))",
        {"id": foto_id, "sede": u.sede_id}).fetchone()
    if not fila:
        raise no_encontrado("La foto")
    return _imagen(fotos.leer(fila["clave"], tamano), publica=False)


@router.delete("/fotos/{foto_id}", status_code=204)
def borrar(foto_id: UUID, request: Request, u: Usuario = Depends(solo_admin),
           conn: Connection = Depends(get_conn)) -> Response:
    fila = _foto_de_sede(conn, foto_id, u.sede_id)
    conn.execute("DELETE FROM foto_objeto WHERE id = %s", (foto_id,))
    fotos.borrar(fila["clave"])
    auditar(conn, u.id, "actualizar", "foto_objeto", foto_id, u.sede_id, ip=ip_cliente(request),
            detalle={"borrada": True, "objeto": str(fila["objeto_id"])})
    return Response(status_code=204)


@router.get("/publico/fotos/{foto_id}/{tamano}", dependencies=[Depends(limite_publico)])
def ver_publica(foto_id: UUID, tamano: Tamano, conn: Connection = Depends(get_conn)) -> Response:
    fila = conn.execute("SELECT clave FROM vista_publica_fotos WHERE id = %s", (foto_id,)).fetchone()
    if not fila:
        raise no_encontrado("La foto")
    return _imagen(fotos.leer(fila["clave"], tamano), publica=True)


# ------------------------------------------------------------------ retención (90 días tras cerrar)
SQL_VENCIDAS = """
SELECT f.id, f.clave FROM foto_objeto f
LEFT JOIN reporte_perdida r ON f.objeto_tipo = 'perdido' AND r.id = f.objeto_id
LEFT JOIN hallazgo h ON f.objeto_tipo = 'hallado' AND h.id = f.objeto_id
WHERE (f.objeto_tipo = 'perdido' AND (r.id IS NULL OR (r.estado NOT IN ('registrado', 'publicado', 'en_coincidencia')
        AND coalesce(r.cerrado_en, r.creado_en + interval '90 days') < now() - interval '90 days')))
   OR (f.objeto_tipo = 'hallado' AND (h.id IS NULL OR (h.estado NOT IN ('registrado', 'publicado', 'en_coincidencia')
        AND coalesce(h.cerrado_en, h.vence_en::timestamptz) < now() - interval '90 days')))
LIMIT 500
"""
LOCK_PURGA = 7_141_002


def purgar(conn: Connection) -> int:
    """Borra las fotos de casos cerrados hace más de 90 días. Devuelve cuántas borró."""
    borradas = 0
    for f in conn.execute(SQL_VENCIDAS).fetchall():
        fotos.borrar(f["clave"])
        conn.execute("DELETE FROM foto_objeto WHERE id = %s", (f["id"],))
        borradas += 1
    return borradas


def iniciar_purga_periodica(cada_horas: float = 12) -> None:
    """Hilo de fondo de la API. Un advisory lock evita que dos copias de la API purguen a la vez."""

    def bucle() -> None:
        time.sleep(60)
        while True:
            try:
                with pool().connection() as conn:
                    if conn.execute("SELECT pg_try_advisory_xact_lock(%s) AS ok", (LOCK_PURGA,)).fetchone()["ok"]:
                        n = purgar(conn)
                        if n:
                            log.info('"fotos purgadas: %s"', n)
            except Exception:  # noqa: BLE001 - p. ej. almacén caído; se reintenta en el próximo ciclo
                log.exception('"purga de fotos falló"')
            time.sleep(cada_horas * 3600)

    threading.Thread(target=bucle, name="purga-fotos", daemon=True).start()


def borrar_de_estudiante(conn: Connection, estudiante_id) -> int:
    """Derecho de supresión: las fotos de los reportes del estudiante se borran de inmediato."""
    filas = conn.execute("SELECT f.id, f.clave FROM foto_objeto f JOIN reporte_perdida r ON r.id = f.objeto_id "
                         "WHERE f.objeto_tipo = 'perdido' AND r.estudiante_id = %s", (estudiante_id,)).fetchall()
    for f in filas:
        fotos.borrar(f["clave"])
        conn.execute("DELETE FROM foto_objeto WHERE id = %s", (f["id"],))
    return len(filas)
