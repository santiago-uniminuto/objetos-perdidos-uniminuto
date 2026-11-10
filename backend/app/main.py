"""Punto de entrada de la API (monolito modular, ADR-001)."""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app import __version__
from app.config import get_settings
from app.db import cerrar_pool
from app.errores import registrar_manejadores
from app.modulos import (
    analitica,
    auditoria,
    auth,
    catalogos,
    coincidencias,
    entregas,
    estudiantes,
    hallazgos,
    publico,
    reportes,
)
from app.salud import router as salud_router

logging.basicConfig(level=logging.INFO, format='{"nivel":"%(levelname)s","msg":%(message)s}')
log = logging.getLogger("api")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    get_settings().validar_produccion()
    yield
    cerrar_pool()


app = FastAPI(
    title="Objetos Perdidos UNIMINUTO",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=ciclo_de_vida,
)
registrar_manejadores(app)


@app.middleware("http")
async def registro_peticiones(request: Request, call_next):
    """Log JSON por petición con id de correlación (RNF-13). Nunca registra cuerpos ni cookies."""
    peticion_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    ms = (time.perf_counter() - inicio) * 1000
    respuesta.headers["x-request-id"] = peticion_id
    log.info('{"id":"%s","metodo":"%s","ruta":"%s","estado":%d,"ms":%.1f}',
             peticion_id, request.method, request.url.path, respuesta.status_code, ms)
    return respuesta


for modulo in (salud_router, auth.router, catalogos.router, estudiantes.router, reportes.router,
               hallazgos.router, publico.router, coincidencias.router, entregas.router, auditoria.router,
               analitica.router):
    app.include_router(modulo, prefix="/api/v1")
