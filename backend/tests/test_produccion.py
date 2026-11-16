"""Revisión de configuración al arrancar fuera de desarrollo (Fase 7)."""

import pytest

from app.config import Settings

CLAVE = "x" * 48


def ajustes(**kw) -> Settings:
    base = {"app_env": "produccion", "secret_key": CLAVE, "cookie_segura": True,
            "url_publica": "https://portatil.tailnet.ts.net", "limite_publico_por_minuto": 60,
            "smtp_host": "smtp.gmail.com",
            "correo_dominios_permitidos": "uniminuto.edu,uniminuto.edu.co"}
    return Settings(_env_file=None, **{**base, **kw})


def test_desarrollo_no_exige_nada():
    assert ajustes(app_env="desarrollo", secret_key="corta",  # noqa: S106 - clave falsa de prueba
                   cookie_segura=False).validar_produccion() == []


def test_produccion_bien_configurada_no_avisa():
    assert ajustes().validar_produccion() == []


@pytest.mark.parametrize("cambio", [{"secret_key": "objetosperdidos"}, {"secret_key": "cambia-esto"},
                                    {"cookie_segura": False}])
def test_lo_inseguro_detiene_la_api(cambio):
    with pytest.raises(RuntimeError):
        ajustes(**cambio).validar_produccion()


def test_lo_dudoso_se_avisa():
    avisos = ajustes(url_publica="http://localhost:8080", limite_publico_por_minuto=1_000_000,
                     smtp_host="mailpit", correo_dominios_permitidos=" ").validar_produccion()
    assert len(avisos) == 4
    assert any("URL_PUBLICA" in a for a in avisos) and any("mailpit" in a for a in avisos)
    assert any("CORREO_DOMINIOS_PERMITIDOS" in a for a in avisos)
