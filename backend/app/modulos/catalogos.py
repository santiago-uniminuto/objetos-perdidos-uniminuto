"""GET /catalogos: sedes, zonas y categorías (público, cacheado)."""

import json

from fastapi import APIRouter, Depends
from psycopg import Connection

from app.cache import get_redis
from app.db import get_conn

router = APIRouter(tags=["catálogos"])


@router.get("/catalogos")
def catalogos(conn: Connection = Depends(get_conn), r=Depends(get_redis)) -> dict:
    guardado = r.get("cache:catalogos")
    if guardado:
        return json.loads(guardado)
    datos = {
        "sedes": conn.execute("SELECT id, codigo, nombre, ciudad FROM sede WHERE activa ORDER BY id").fetchall(),
        "zonas": conn.execute("SELECT id, sede_id, nombre FROM zona WHERE activa ORDER BY sede_id, id").fetchall(),
        "categorias": conn.execute("SELECT id, codigo, nombre, es_documento FROM categoria ORDER BY id").fetchall(),
    }
    r.set("cache:catalogos", json.dumps(datos), ex=300)
    return datos
