"""Vista pública sin login (HU-05). Lista blanca de campos (ADR-007), caché y límite por IP."""

import hashlib
import json
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from psycopg import Connection
from pydantic import BaseModel

from app.cache import get_redis
from app.config import get_settings
from app.db import get_conn
from app.errores import ErrorApp, no_encontrado
from app.seguridad import decodificar_cursor, ip_cliente, paginar

router = APIRouter(prefix="/publico", tags=["público"])

INSTRUCCIONES = ("Si este objeto es tuyo o lo encontraste, acércate a la oficina de objetos perdidos "
                 "de tu sede con tu carné. Nunca entregamos objetos sin verificar al dueño.")


class ObjetoPublico(BaseModel):
    """ÚNICOS campos que salen a la página pública. Agregar uno aquí es una decisión de privacidad."""

    tipo: Literal["perdido", "hallado"]
    id: UUID
    categoria: str
    zona: str | None
    descripcion: str
    fecha: date
    estado: Literal["publicado", "en_coincidencia"]
    publicado_en: datetime


def limite_publico(request: Request, r=Depends(get_redis)) -> None:
    """60 peticiones por minuto por IP (RNF-07)."""
    llave = f"limite:{ip_cliente(request)}:{int(datetime.now().timestamp() // 60)}"
    n = r.incr(llave)
    if n == 1:
        r.expire(llave, 70)
    if n > get_settings().limite_publico_por_minuto:
        raise ErrorApp(429, "demasiadas_peticiones", "Demasiadas consultas; espera un minuto")


def _publico(fila: dict) -> dict:
    return ObjetoPublico(tipo=fila["tipo"], id=fila["id"], categoria=fila["categoria"], zona=fila["zona"],
                         descripcion=fila["descripcion_publica"], fecha=fila["fecha"], estado=fila["estado"],
                         publicado_en=fila["creado_en"]).model_dump(mode="json")


@router.get("/objetos", dependencies=[Depends(limite_publico)])
def listar(tipo: Literal["perdido", "hallado"] | None = None, categoria: str | None = Query(None, max_length=30),
           zona: int | None = None, desde: date | None = None, hasta: date | None = None,
           sede: int = 1, cursor: str | None = None, limite: int = Query(20, ge=1, le=50),
           conn: Connection = Depends(get_conn), r=Depends(get_redis)) -> dict:
    clave = "cache:publico:" + hashlib.sha256(
        json.dumps([tipo, categoria, zona, str(desde), str(hasta), sede, cursor, limite]).encode()).hexdigest()
    guardado = r.get(clave)
    if guardado:
        return json.loads(guardado)

    filtros, params = ["sede_id = %s"], [sede]
    for columna, valor in (("tipo", tipo), ("categoria_codigo", categoria), ("zona_id", zona)):
        if valor is not None:
            filtros.append(f"{columna} = %s")
            params.append(valor)
    if desde:
        filtros.append("fecha >= %s")
        params.append(desde)
    if hasta:
        filtros.append("fecha <= %s")
        params.append(hasta)
    if cursor:
        c_fecha, c_id = decodificar_cursor(cursor)
        filtros.append("(creado_en, id) < (%s, %s)")
        params += [c_fecha, c_id]
    filas = conn.execute(
        "SELECT * FROM vista_publica_objetos WHERE " + " AND ".join(filtros) +
        " ORDER BY creado_en DESC, id DESC LIMIT %s", [*params, limite + 1],
    ).fetchall()
    items, siguiente = paginar(filas, limite)
    respuesta = {"items": [_publico(f) for f in items], "siguiente": siguiente,
                 "instrucciones": INSTRUCCIONES}
    r.set(clave, json.dumps(respuesta), ex=get_settings().cache_publico_segundos)
    return respuesta


@router.get("/objetos/{objeto_id}", dependencies=[Depends(limite_publico)])
def detalle(objeto_id: UUID, conn: Connection = Depends(get_conn)) -> dict:
    fila = conn.execute("SELECT * FROM vista_publica_objetos WHERE id = %s", (objeto_id,)).fetchone()
    if not fila:
        raise no_encontrado("El objeto")
    return {**_publico(fila), "instrucciones": INSTRUCCIONES}
