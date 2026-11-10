"""Autenticación de administradores: Argon2 para contraseñas y JWT firmado en cookie httpOnly.

- La cookie es httpOnly (JavaScript no la lee), Secure y SameSite=Strict (mitiga CSRF).
- También se acepta `Authorization: Bearer <token>` para clientes de API y pruebas.
- Bloqueo tras N intentos fallidos (HU-01).
"""

import base64
import ipaddress
import time
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, Request

from app.config import get_settings
from app.errores import ErrorApp

COOKIE = "sesion"
_hasher = PasswordHasher()


def hashear(contrasena: str) -> str:
    return _hasher.hash(contrasena)


def verificar(hash_: str, contrasena: str) -> bool:
    try:
        return _hasher.verify(hash_, contrasena)
    except VerificationError:
        return False


@dataclass(frozen=True)
class Usuario:
    id: UUID
    rol: str
    sede_id: int | None
    nombre: str

    @property
    def es_admin(self) -> bool:
        return self.rol == "admin_sede"


def emitir_token(u: Usuario) -> str:
    cfg = get_settings()
    ahora = int(time.time())
    datos = {"sub": str(u.id), "rol": u.rol, "sede": u.sede_id, "nombre": u.nombre,
             "iat": ahora, "exp": ahora + cfg.sesion_minutos * 60}
    return jwt.encode(datos, cfg.secret_key, algorithm="HS256")


def _token_de(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:]
    return request.cookies.get(COOKIE)


def usuario_actual(request: Request) -> Usuario:
    token = _token_de(request)
    if not token:
        raise ErrorApp(401, "no_autenticado", "Inicia sesión")
    try:
        d = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise ErrorApp(401, "sesion_invalida", "La sesión expiró o no es válida") from exc
    return Usuario(UUID(d["sub"]), d["rol"], d.get("sede"), d.get("nombre", ""))


def solo_admin(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if not u.es_admin:
        raise ErrorApp(403, "prohibido", "Solo un administrador de sede puede hacer esto")
    return u


def solo_auditor(u: Usuario = Depends(usuario_actual)) -> Usuario:
    if u.rol != "auditor":
        raise ErrorApp(403, "prohibido", "Solo el rol auditor puede consultar la auditoría")
    return u


def ip_cliente(request: Request) -> str | None:
    """IP real: Caddy la pone en X-Forwarded-For. Se valida: un encabezado falso no debe romper la auditoría."""
    reenviada = request.headers.get("x-forwarded-for")
    candidata = reenviada.split(",")[0].strip() if reenviada else (request.client.host if request.client else None)
    try:
        return str(ipaddress.ip_address(candidata)) if candidata else None
    except ValueError:
        return None


# ------------------------------------------------------------------ cursores
def codificar_cursor(creado_en: datetime, id_: UUID) -> str:
    return base64.urlsafe_b64encode(f"{creado_en.isoformat()}|{id_}".encode()).decode()


def decodificar_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        fecha, id_ = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(fecha), UUID(id_)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ErrorApp(422, "cursor_invalido", "El cursor de paginación no es válido") from exc


def paginar(filas: list[dict], limite: int) -> tuple[list[dict], str | None]:
    """Se piden limite+1 filas: si sobra una, hay página siguiente y el cursor es la última mostrada."""
    if len(filas) <= limite:
        return filas, None
    ultima = filas[limite - 1]
    return filas[:limite], codificar_cursor(ultima["creado_en"], ultima["id"])
