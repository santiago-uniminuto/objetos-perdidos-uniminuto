"""Envío de correo por SMTP (Mailpit en desarrollo, Gmail con contraseña de aplicación en producción)."""

import smtplib
from email.message import EmailMessage

from harness.config import Config


class EnviadorSMTP:
    def __init__(self, cfg: Config):
        self.cfg = cfg

    def enviar(self, destino: str, asunto: str, cuerpo: str) -> str:
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
