"""Envío de correo por SMTP (Mailpit en desarrollo, Gmail con contraseña de aplicación en producción)."""

import re
import smtplib
from email.message import EmailMessage

from harness.config import Config

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


class EnviadorSMTP:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def enviar(self, destino: str, asunto: str, cuerpo: str) -> str:
        """Devuelve "enviado" o "bloqueado_dominio" (en ese caso no se conecta al SMTP)."""
        if not dominio_permitido(destino, self.cfg.correo_dominios_permitidos):
            return "bloqueado_dominio"
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = self.cfg.smtp_from, destino, asunto
        msg.set_content(cuerpo)
        with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port, timeout=15) as smtp:
            if self.cfg.smtp_tls:
                smtp.starttls()
            if self.cfg.smtp_user:
                smtp.login(self.cfg.smtp_user, self.cfg.smtp_password)
            smtp.send_message(msg)
        return "enviado"  # la traza nunca guarda el destinatario