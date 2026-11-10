"""Formato único de error: {"codigo", "mensaje", "detalle"} (Fase 2, contrato de API)."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorApp(Exception):
    def __init__(self, estado: int, codigo: str, mensaje: str, detalle: object = None):
        self.estado, self.codigo, self.mensaje, self.detalle = estado, codigo, mensaje, detalle


def no_encontrado(que: str) -> ErrorApp:
    return ErrorApp(404, "no_encontrado", f"{que} no existe o no pertenece a tu sede")


def conflicto(mensaje: str, detalle: object = None) -> ErrorApp:
    return ErrorApp(409, "conflicto", mensaje, detalle)


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorApp)
    async def _app(_: Request, exc: ErrorApp):
        return JSONResponse(status_code=exc.estado,
                            content={"codigo": exc.codigo, "mensaje": exc.mensaje, "detalle": exc.detalle})

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError):
        detalle = [{"campo": ".".join(str(p) for p in e["loc"][1:]), "error": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422,
                            content={"codigo": "validacion", "mensaje": "Datos inválidos", "detalle": detalle})
