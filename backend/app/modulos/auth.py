"""POST /auth/login · POST /auth/logout · GET /auth/yo"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field

from app.config import get_settings
from app.db import pool
from app.errores import ErrorApp
from app.registro import auditar
from app.seguridad import COOKIE, Usuario, emitir_token, ip_cliente, usuario_actual, verificar

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
