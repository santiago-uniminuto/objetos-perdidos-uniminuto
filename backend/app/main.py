"""Punto de entrada de la API. Los módulos de dominio se agregan en la Fase 5."""

from fastapi import FastAPI

from app import __version__
from app.salud import router as salud_router

app = FastAPI(
    title="Objetos Perdidos UNIMINUTO",
    version=__version__,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.include_router(salud_router, prefix="/api/v1")
