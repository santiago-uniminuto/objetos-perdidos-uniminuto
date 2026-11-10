"""Envío de correos del backend (por ahora, solo el enlace para restablecer la contraseña)."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

log = logging.getLogger("correo")


def enviar(destinatario: str, asunto: str, cuerpo: str) -> None:
    cfg = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg.smtp_from, destinatario, asunto
    msg.set_content(cuerpo)
    with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15) as s:
        if cfg.smtp_tls:
            s.starttls()
        if cfg.smtp_user:
            s.login(cfg.smtp_user, cfg.smtp_password)
        s.send_message(msg)
