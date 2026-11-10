"""Restablecimiento de contraseña con enlace de un solo uso (ADR-016).

- El token sale de `secrets` (256 bits) y en la base solo queda su SHA-256.
- Vence en RESTABLECER_MINUTOS (30) y se puede usar una vez; pedir uno nuevo anula los anteriores.
- La respuesta de "olvidé mi contraseña" es siempre la misma: no revela qué correos existen.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.errores import ErrorApp


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def validar_nueva(contrasena: str, email: str) -> None:
    cfg = get_settings()
    if len(contrasena) < cfg.contrasena_min:
        raise ErrorApp(422, "contrasena_debil", f"La contraseña debe tener al menos {cfg.contrasena_min} caracteres")
    if email.split("@")[0].lower() in contrasena.lower():
        raise ErrorApp(422, "contrasena_debil", "La contraseña no puede contener tu correo")


def crear_enlace(conn, usuario_id, origen: str) -> str:
    """Anula los enlaces pendientes del usuario y crea uno nuevo. Devuelve la URL con el token."""
    cfg = get_settings()
    token = secrets.token_urlsafe(32)
    conn.execute("UPDATE restablecimiento_contrasena SET usado_en = now() WHERE usuario_id = %s AND usado_en IS NULL",
                 (usuario_id,))
    conn.execute("INSERT INTO restablecimiento_contrasena (usuario_id, token_hash, vence_en, origen) "
                 "VALUES (%s, %s, %s, %s)",
                 (usuario_id, _hash(token), datetime.now(UTC) + timedelta(minutes=cfg.restablecer_minutos), origen))
    return f"{cfg.url_publica.rstrip('/')}/admin/restablecer?token={token}"


def consumir(conn, token: str) -> dict:
    """Marca el enlace como usado y devuelve el usuario. Error si no existe, venció o ya se usó."""
    fila = conn.execute(
        "SELECT r.id, r.vence_en, r.usado_en, u.id AS usuario_id, u.email, u.sede_id, u.activo "
        "FROM restablecimiento_contrasena r JOIN usuario u ON u.id = r.usuario_id "
        "WHERE r.token_hash = %s FOR UPDATE OF r", (_hash(token),)).fetchone()
    if not fila or fila["usado_en"] or fila["vence_en"] < datetime.now(UTC) or not fila["activo"]:
        raise ErrorApp(400, "enlace_invalido", "El enlace no es válido o ya venció. Pide uno nuevo.")
    conn.execute("UPDATE restablecimiento_contrasena SET usado_en = now() WHERE id = %s", (fila["id"],))
    return fila
