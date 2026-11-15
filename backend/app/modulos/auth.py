"""Sesión y contraseñas del personal (admin de sede y auditor).

POST /auth/login · POST /auth/logout · GET /auth/yo
POST /auth/olvide-contrasena · POST /auth/restablecer-contrasena · POST /auth/cambiar-contrasena
No hay registro abierto: las cuentas se crean por consola (python -m app.crear_usuario).
"""

import asyncio
import logging
import os
import weakref
from datetime import UTC, datetime

import anyio
from fastapi import APIRouter, Depends, Request, Response
from psycopg import Connection
from pydantic import BaseModel, EmailStr, Field

from app import contrasenas, correo
from app.cache import get_redis
from app.config import get_settings
from app.db import get_conn, pool
from app.errores import ErrorApp
from app.registro import auditar
from app.seguridad import COOKIE, Usuario, emitir_token, hashear, ip_cliente, usuario_actual, verificar

log = logging.getLogger("auth")

router = APIRouter(prefix="/auth", tags=["autenticación"])


class Login(BaseModel):
    email: EmailStr
    contrasena: str = Field(min_length=1, max_length=200)


# argon2 es caro a propósito (~0,2-2 s de CPU). Se calcula con su propio límite de hilos: los logins en
# ráfaga esperan su turno SIN ocupar los hilos de la API ni conexiones a la base (Fase 6, ADR-021).
# Como mucho la mitad de los núcleos (entre 1 y 4): siempre queda CPU para el resto de la API.
MAX_HASH_SIMULTANEOS = max(1, min(4, (os.cpu_count() or 2) // 2))
_limitadores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, anyio.CapacityLimiter]" = \
    weakref.WeakKeyDictionary()


def _limitador() -> anyio.CapacityLimiter:
    """Uno por bucle de eventos: en producción hay uno solo; las pruebas crean varios."""
    bucle = asyncio.get_running_loop()
    if bucle not in _limitadores:
        _limitadores[bucle] = anyio.CapacityLimiter(MAX_HASH_SIMULTANEOS)
    return _limitadores[bucle]


@router.post("/login")
async def login(datos: Login, request: Request, response: Response) -> dict:
    """Leer usuario → verificar argon2 (fuera de la base) → registrar el resultado en una sentencia atómica.

    Antes, el login bloqueaba la fila del usuario (FOR UPDATE) y calculaba argon2 con ese bloqueo, la
    conexión y el hilo tomados: 20 logins a la misma cuenta (o un atacante con contraseñas erradas)
    agotaban hilos y conexiones y congelaban toda la API.
    """
    cfg = get_settings()
    fila = await anyio.to_thread.run_sync(_leer_usuario, datos.email)
    # Mismo mensaje para usuario inexistente y contraseña errada: no revela qué correos existen
    error = ErrorApp(401, "credenciales", "Correo o contraseña incorrectos")
    if not fila or not fila["activo"]:
        raise error
    if fila["bloqueado_hasta"] and fila["bloqueado_hasta"] > datetime.now(UTC):
        raise ErrorApp(423, "bloqueado", "Cuenta bloqueada temporalmente por intentos fallidos")

    ok = await anyio.to_thread.run_sync(verificar, fila["hash_contrasena"], datos.contrasena, limiter=_limitador())
    ip = ip_cliente(request)
    if not ok:
        await anyio.to_thread.run_sync(_registrar_fallo, fila, ip)
        raise error
    perfil = await anyio.to_thread.run_sync(_registrar_exito, fila, ip)
    u = Usuario(fila["id"], fila["rol"], fila["sede_id"], fila["nombre"])
    response.set_cookie(COOKIE, emitir_token(u), max_age=cfg.sesion_minutos * 60, httponly=True,
                        secure=cfg.cookie_segura, samesite="strict", path="/")
    # El token NO va en el cuerpo: vive solo en la cookie httpOnly, fuera del alcance de JavaScript
    return {"usuario": perfil}


def _leer_usuario(email: str) -> dict | None:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT id, sede_id, nombre, rol, hash_contrasena, activo, bloqueado_hasta FROM usuario "
            "WHERE lower(email) = lower(%s)", (email,)).fetchone()


def _registrar_fallo(fila: dict, ip: str | None) -> None:
    """Suma el intento y, al llegar al máximo, bloquea: todo en una sentencia (sin carreras entre logins)."""
    cfg = get_settings()
    with pool().connection() as conn:
        r = conn.execute(
            "UPDATE usuario SET "
            "intentos_fallidos = CASE WHEN intentos_fallidos + 1 >= %(max)s THEN 0 ELSE intentos_fallidos + 1 END, "
            "bloqueado_hasta = CASE WHEN intentos_fallidos + 1 >= %(max)s "
            "                  THEN now() + make_interval(mins => %(min)s) ELSE bloqueado_hasta END "
            "WHERE id = %(id)s RETURNING bloqueado_hasta > now() AS bloqueado",
            {"max": cfg.max_intentos_login, "min": cfg.bloqueo_minutos, "id": fila["id"]}).fetchone()
        auditar(conn, fila["id"], "login_fallido", "usuario", fila["id"], fila["sede_id"], ip=ip,
                detalle={"bloqueado": bool(r and r["bloqueado"])})


def _registrar_exito(fila: dict, ip: str | None) -> dict:
    with pool().connection() as conn:
        conn.execute("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s", (fila["id"],))
        auditar(conn, fila["id"], "login", "usuario", fila["id"], fila["sede_id"], ip=ip)
        return _perfil(conn, Usuario(fila["id"], fila["rol"], fila["sede_id"], fila["nombre"]))


def _perfil(conn: Connection, u: Usuario) -> dict:
    """Lo que el panel muestra del usuario: incluye el nombre de su sede (el auditor no tiene)."""
    sede = conn.execute("SELECT nombre, ciudad FROM sede WHERE id = %s", (u.sede_id,)).fetchone() \
        if u.sede_id is not None else None
    return {"id": u.id, "nombre": u.nombre, "rol": u.rol, "sede_id": u.sede_id,
            "sede": sede["nombre"] if sede else None, "ciudad": sede["ciudad"] if sede else None}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/yo")
def yo(u: Usuario = Depends(usuario_actual), conn: Connection = Depends(get_conn)) -> dict:
    return _perfil(conn, u)


# ------------------------------------------------------------------ contraseñas
MENSAJE_OLVIDE = ("Si el correo pertenece a una cuenta activa, te enviamos un enlace para crear una contraseña "
                  "nueva. Vence en 30 minutos. Revisa también la carpeta de spam.")
ASUNTO = "Restablecer tu contraseña · Objetos Perdidos UNIMINUTO"


class Olvide(BaseModel):
    email: EmailStr


class Restablecer(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    contrasena: str = Field(min_length=1, max_length=200)


class Cambiar(BaseModel):
    actual: str = Field(min_length=1, max_length=200)
    nueva: str = Field(min_length=1, max_length=200)


def _limitar(r, llave: str, maximo: int, segundos: int) -> bool:
    n = r.incr(llave)
    if n == 1:
        r.expire(llave, segundos)
    return n <= maximo


@router.post("/olvide-contrasena", status_code=202)
def olvide(datos: Olvide, request: Request, r=Depends(get_redis)) -> dict:
    ip = ip_cliente(request)
    if not _limitar(r, f"olvide:ip:{ip}", 5, 900):
        raise ErrorApp(429, "demasiadas_peticiones", "Demasiadas solicitudes; intenta en 15 minutos")
    # Por correo se limita en silencio: la respuesta no cambia, así no se puede saber si existe
    if not _limitar(r, f"olvide:correo:{datos.email.lower()}", 3, 3600):
        return {"mensaje": MENSAJE_OLVIDE}
    with pool().connection() as conn:
        u = conn.execute("SELECT id, sede_id, nombre FROM usuario WHERE lower(email) = lower(%s) AND activo",
                         (datos.email,)).fetchone()
        if u is None:
            return {"mensaje": MENSAJE_OLVIDE}
        enlace = contrasenas.crear_enlace(conn, u["id"], "correo")
        auditar(conn, u["id"], "solicitud_restablecimiento", "usuario", u["id"], u["sede_id"], ip=ip)
        conn.commit()
    minutos = get_settings().restablecer_minutos
    try:
        correo.enviar(datos.email, ASUNTO,
                      f"Hola, {u['nombre']}.\n\nPediste restablecer tu contraseña. Abre este enlace (vence en "
                      f"{minutos} minutos y sirve una sola vez):\n\n{enlace}\n\nSi no fuiste tú, ignora este "
                      f"correo: tu contraseña actual sigue funcionando.\n")
    except Exception as exc:  # noqa: BLE001 - la respuesta no revela si el correo existe ni si falló el envío
        log.error("no se pudo enviar el correo de restablecimiento: %s", type(exc).__name__)
    return {"mensaje": MENSAJE_OLVIDE}


@router.post("/restablecer-contrasena")
def restablecer(datos: Restablecer, request: Request, conn: Connection = Depends(get_conn)) -> dict:
    fila = contrasenas.consumir(conn, datos.token)
    contrasenas.validar_nueva(datos.contrasena, fila["email"])
    # También desbloquea la cuenta: quien olvidó la clave suele haberse bloqueado intentando
    conn.execute("UPDATE usuario SET hash_contrasena = %s, intentos_fallidos = 0, bloqueado_hasta = NULL "
                 "WHERE id = %s", (hashear(datos.contrasena), fila["usuario_id"]))
    auditar(conn, fila["usuario_id"], "cambio_contrasena", "usuario", fila["usuario_id"], fila["sede_id"],
            ip=ip_cliente(request), detalle={"via": "enlace"})
    return {"mensaje": "Contraseña actualizada. Ya puedes iniciar sesión."}


@router.post("/cambiar-contrasena")
def cambiar(datos: Cambiar, request: Request, u: Usuario = Depends(usuario_actual),
            conn: Connection = Depends(get_conn)) -> dict:
    fila = conn.execute("SELECT email, hash_contrasena FROM usuario WHERE id = %s", (u.id,)).fetchone()
    if not verificar(fila["hash_contrasena"], datos.actual):
        raise ErrorApp(400, "contrasena_actual", "La contraseña actual no es correcta")
    contrasenas.validar_nueva(datos.nueva, fila["email"])
    conn.execute("UPDATE usuario SET hash_contrasena = %s WHERE id = %s", (hashear(datos.nueva), u.id))
    auditar(conn, u.id, "cambio_contrasena", "usuario", u.id, u.sede_id, ip=ip_cliente(request),
            detalle={"via": "sesion"})
    return {"mensaje": "Contraseña actualizada."}
