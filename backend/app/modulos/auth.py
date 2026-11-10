"""Sesión y contraseñas del personal (admin de sede y auditor).

POST /auth/login · POST /auth/logout · GET /auth/yo
POST /auth/olvide-contrasena · POST /auth/restablecer-contrasena · POST /auth/cambiar-contrasena
No hay registro abierto: las cuentas se crean por consola (python -m app.crear_usuario).
"""

import logging
from datetime import UTC, datetime, timedelta

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


@router.post("/login")
def login(datos: Login, request: Request, response: Response) -> dict:
    # Transacción propia: un intento fallido debe quedar guardado aunque la respuesta sea un error
    with pool().connection() as conn:
        resultado = _login(conn, datos, request)
    if isinstance(resultado, ErrorApp):
        raise resultado
    u, token = resultado
    cfg = get_settings()
    response.set_cookie(COOKIE, token, max_age=cfg.sesion_minutos * 60, httponly=True,
                        secure=cfg.cookie_segura, samesite="strict", path="/")
    # El token NO va en el cuerpo: vive solo en la cookie httpOnly, fuera del alcance de JavaScript
    return {"usuario": {"id": u.id, "nombre": u.nombre, "rol": u.rol, "sede_id": u.sede_id}}


def _login(conn, datos: Login, request: Request) -> tuple[Usuario, str] | ErrorApp:
    cfg = get_settings()
    fila = conn.execute(
        "SELECT id, sede_id, nombre, rol, hash_contrasena, activo, intentos_fallidos, bloqueado_hasta "
        "FROM usuario WHERE lower(email) = lower(%s) FOR UPDATE",
        (datos.email,),
    ).fetchone()
    ahora = datetime.now(UTC)
    # Mismo mensaje para usuario inexistente y contraseña errada: no revela qué correos existen
    error = ErrorApp(401, "credenciales", "Correo o contraseña incorrectos")
    if not fila or not fila["activo"]:
        return error
    if fila["bloqueado_hasta"] and fila["bloqueado_hasta"] > ahora:
        return ErrorApp(423, "bloqueado", "Cuenta bloqueada temporalmente por intentos fallidos")

    if not verificar(fila["hash_contrasena"], datos.contrasena):
        intentos = fila["intentos_fallidos"] + 1
        bloqueo = ahora + timedelta(minutes=cfg.bloqueo_minutos) if intentos >= cfg.max_intentos_login else None
        conn.execute("UPDATE usuario SET intentos_fallidos = %s, bloqueado_hasta = %s WHERE id = %s",
                     (0 if bloqueo else intentos, bloqueo, fila["id"]))
        auditar(conn, fila["id"], "login_fallido", "usuario", fila["id"], fila["sede_id"], ip=ip_cliente(request),
                detalle={"bloqueado": bool(bloqueo)})
        conn.commit()
        return error

    conn.execute("UPDATE usuario SET intentos_fallidos = 0, bloqueado_hasta = NULL WHERE id = %s", (fila["id"],))
    auditar(conn, fila["id"], "login", "usuario", fila["id"], fila["sede_id"], ip=ip_cliente(request))
    conn.commit()
    u = Usuario(fila["id"], fila["rol"], fila["sede_id"], fila["nombre"])
    return u, emitir_token(u)


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/yo")
def yo(u: Usuario = Depends(usuario_actual)) -> dict:
    return {"id": u.id, "nombre": u.nombre, "rol": u.rol, "sede_id": u.sede_id}


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
