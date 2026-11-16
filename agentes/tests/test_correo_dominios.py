"""Lista blanca de dominios en el enviador SMTP de los agentes (sin SMTP real)."""

import pytest

from harness import correo
from harness.config import Config
from harness.correo import EnviadorSMTP, dominio_permitido

PERMITIDOS = "uniminuto.edu,uniminuto.edu.co"


@pytest.mark.parametrize("direccion,esperado", [
    ("ana@uniminuto.edu.co", True),
    ("ANA@UNIMINUTO.EDU", True),
    ("ana@gmail.com", False),
    ("ana@falso-uniminuto.edu.co", False),
    ("ana@correo.uniminuto.edu.co", False),
    ("ana@evil.com,otra@uniminuto.edu.co", False),
    ("", False),
])
def test_dominio_permitido(direccion, esperado):
    assert dominio_permitido(direccion, PERMITIDOS) is esperado


def test_lista_vacia_no_restringe():
    assert dominio_permitido("cualquiera@pruebas.edu.co", "")


def test_bloquea_sin_conectar(monkeypatch):
    monkeypatch.setenv("CORREO_DOMINIOS_PERMITIDOS", PERMITIDOS)

    def no_debe_conectar(*_a, **_k):
        raise AssertionError("no debe abrir conexión SMTP")

    monkeypatch.setattr(correo.smtplib, "SMTP", no_debe_conectar)
    assert EnviadorSMTP(Config()).enviar("ana@gmail.com", "Asunto", "Cuerpo") == "bloqueado_dominio"


def test_envia_si_esta_permitido(monkeypatch):
    monkeypatch.setenv("CORREO_DOMINIOS_PERMITIDOS", PERMITIDOS)
    enviados = []

    class SMTPFalso:
        def __init__(self, *_a, **_k): ...
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def send_message(self, msg): enviados.append(msg)

    monkeypatch.setattr(correo.smtplib, "SMTP", SMTPFalso)
    assert EnviadorSMTP(Config()).enviar("ana@uniminuto.edu.co", "Asunto", "Cuerpo") == "enviado"
    assert enviados[0]["To"] == "ana@uniminuto.edu.co"