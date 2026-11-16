"""Envío de correos del backend (por ahora, solo el enlace para restablecer la contraseña)."""

import logging
import re
import smtplib
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger("correo")

# Una sola dirección: sin espacios, comas ni <>; evita "a@x.com,b@uniminuto.edu.co" (dos destinatarios)
_DIRECCION = re.compile(r"[^@\s,;<>]+@([^@\s,;<>]+)")


def dominio_permitido(correo: str, permitidos: str) -> bool:
    """True si el dominio de `correo` está en la lista (comparación exacta, sin distinguir mayúsculas).

    Lista vacía = sin restricción. No se usa endswith: aceptaría "falso-uniminuto.edu.co".
    """
    lista = {d.strip().lower().lstrip("@") for d in permitidos.split(",") if d.strip()}
    if not lista:
        return True
    m = _DIRECCION.fullmatch(correo.strip())
    return m is not None and m.group(1).lower() in lista


def enviar(destinatario: str, asunto: str, cuerpo: str) -> bool:
    """Envía el correo. Devuelve False (sin conectarse al SMTP) si el dominio no está permitido."""
    cfg = get_settings()
    if not dominio_permitido(destinatario, cfg.correo_dominios_permitidos):
        log.warning("correo no enviado: el dominio del destinatario no está permitido")
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg.smtp_from, destinatario, asunto
    msg.set_content(cuerpo)
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as s:
        if cfg.smtp_tls:
            s.starttls()
        if cfg.smtp_user:
            s.login(cfg.smtp_user, cfg.smtp_password)
        s.send_message(msg)
    return True
