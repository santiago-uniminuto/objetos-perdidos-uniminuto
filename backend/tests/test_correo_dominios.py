"""Lista blanca de dominios para el correo (sin base de datos ni SMTP real)."""

import pytest
from pydantic import ValidationError

from app import correo
from app.config import get_settings
from app.modulos.estudiantes import EstudianteNuevo

PERMITIDOS = "uniminuto.edu, uniminuto.edu.co"


@pytest.mark.parametrize("direccion", [
    "ana@uniminuto.edu.co", "ana@uniminuto.edu", "ANA@UniMinuto.EDU.CO",
])
def test_dominios_permitidos(direccion):
    assert correo.dominio_permitido(direccion, PERMITIDOS)


@pytest.mark.parametrize("direccion", [
    "ana@gmail.com",
    "ana@falso-uniminuto.edu.co",           # no basta con terminar igual
    "ana@uniminuto.edu.co.evil.com",
    "ana@correo.uniminuto.edu.co",          # subdominios: solo si se agregan a la lista
    "ana@evil.com,otra@uniminuto.edu.co",   # dos destinatarios en un mismo valor
    "ana@evil.com <ana@uniminuto.edu.co>",
    "sin-arroba",
    "",
])
def test_dominios_bloqueados(direccion):
    assert not correo.dominio_permitido(direccion, PERMITIDOS)


def test_lista_vacia_no_restringe():
    assert correo.dominio_permitido("cualquiera@pruebas.edu.co", "")


def test_enviar_no_conecta_si_el_dominio_no_esta_permitido(monkeypatch):
    monkeypatch.setenv("CORREO_DOMINIOS_PERMITIDOS", PERMITIDOS)
    get_settings.cache_clear()

    def no_debe_conectar(*_a, **_k):
        raise AssertionError("no debe abrir conexión SMTP")

    monkeypatch.setattr(correo.smtplib, "SMTP", no_debe_conectar)
    try:
        assert correo.enviar("ana@gmail.com", "Asunto", "Cuerpo") is False
    finally:
        get_settings.cache_clear()


def test_enviar_envia_si_el_dominio_esta_permitido(monkeypatch):
    monkeypatch.setenv("CORREO_DOMINIOS_PERMITIDOS", PERMITIDOS)
    get_settings.cache_clear()
    enviados = []

    class SMTPFalso:
        def __init__(self, *_a, **_k): ...
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def send_message(self, msg): enviados.append(msg)

    monkeypatch.setattr(correo.smtplib, "SMTP", SMTPFalso)
    try:
        assert correo.enviar("ana@uniminuto.edu.co", "Asunto", "Cuerpo") is True
    finally:
        get_settings.cache_clear()
    assert len(enviados) == 1 and enviados[0]["To"] == "ana@uniminuto.edu.co"


def _estudiante(correo_institucional):
    return EstudianteNuevo(tipo_documento="CC", numero_documento="1234567890", nombres="Ana",
                           apellidos="Pérez", correo_institucional=correo_institucional)


def test_registro_de_estudiante_exige_dominio_institucional(monkeypatch):
    monkeypatch.setenv("CORREO_DOMINIOS_PERMITIDOS", PERMITIDOS)
    get_settings.cache_clear()
    try:
        assert _estudiante("ana@uniminuto.edu.co").correo_institucional == "ana@uniminuto.edu.co"
        assert _estudiante(None).correo_institucional is None
        with pytest.raises(ValidationError, match="institucional"):
            _estudiante("ana@gmail.com")
    finally:
        get_settings.cache_clear()