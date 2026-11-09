import json

import pytest
from pydantic import ValidationError

from ia.esquemas import ObjetoNormalizado, texto_canonico
from ia.normalizador import con_llm, heuristica
from ia.proveedores import Uso
from ia.puntaje import UMBRAL_SUGERENCIA, calcular


def test_heuristica_extrae_tipo_marca_y_color_canonico():
    f = heuristica("Perdí mi termo stanly azul marino con sticker de un gato", "botellas")
    assert f.tipo == "termo"
    assert f.marca == "stanley"           # corrige la marca mal escrita
    assert f.colores == ["azul"]          # azul marino -> azul
    assert any("sticker" in r for r in f.rasgos)


def test_sinonimos_de_tipo_quedan_iguales():
    a = heuristica("Se encontró un morral negro", "accesorios")
    b = heuristica("Perdí mi mochila negra", "accesorios")
    assert a.tipo == b.tipo == "maleta"
    assert texto_canonico(a) == texto_canonico(b)


def test_esquema_rechaza_categoria_inventada_y_limpia_colores():
    with pytest.raises(ValidationError):
        ObjetoNormalizado(categoria="armas", tipo="x", resumen="x")
    f = ObjetoNormalizado(categoria="ropa", tipo=" Chaqueta ", colores=["Azul Oscuro", "fosforescente", "azul"],
                          resumen="x")
    assert f.tipo == "chaqueta" and f.colores == ["azul"]


def _ficha(**k):
    base = {"categoria": "botellas", "tipo": "termo", "resumen": "x"}
    return ObjetoNormalizado(**{**base, **k})


def test_puntaje_premia_coincidencia_y_castiga_marca_distinta():
    a = _ficha(marca="stanley", colores=["azul"])
    igual = calcular(0.9, a, _ficha(marca="stanley", colores=["azul"]), dias=1, misma_zona=True)
    otra_marca = calcular(0.9, a, _ficha(marca="contigo", colores=["azul"]), dias=1, misma_zona=True)
    assert igual.total >= UMBRAL_SUGERENCIA
    assert otra_marca.total < igual.total
    assert otra_marca.penalizacion == 0.7


def test_puntaje_hallado_antes_de_perdido_es_casi_imposible():
    a = _ficha(colores=["azul"])
    assert calcular(0.95, a, a, dias=-10, misma_zona=True).tiempo == 0.0


class ChatFalso:
    """Simula un LLM: la primera respuesta es inválida, la segunda es correcta."""

    def __init__(self, respuestas):
        self.respuestas = list(respuestas)
        self.llamadas = 0

    def completar(self, mensajes, **_):
        self.llamadas += 1
        return self.respuestas.pop(0), Uso(10, 5, 1.0)


def test_llm_reintenta_una_vez_y_valida():
    buena = json.dumps({"categoria": "botellas", "tipo": "Termo", "marca": "Stanley", "colores": ["azul marino"],
                        "material": None, "rasgos": [], "resumen": "Termo azul"})
    chat = ChatFalso(["no sé", buena])
    ficha, meta = con_llm("termo azul", "botellas", chat)
    assert meta["estado"] == "ok" and meta["intentos"] == 2
    assert ficha.marca == "stanley" and ficha.colores == ["azul"]


def test_llm_que_falla_dos_veces_usa_respaldo():
    chat = ChatFalso(["basura", '{"categoria": "botellas"}'])
    ficha, meta = con_llm("termo azul stanley", "botellas", chat)
    assert meta["estado"] == "respaldo"
    assert ficha.tipo == "termo"


def test_llm_no_puede_cambiar_la_categoria():
    respuesta = json.dumps({"categoria": "electronicos", "tipo": "celular", "colores": ["dorado"],
                            "rasgos": [], "resumen": "x"})
    ficha, _ = con_llm("termo", "botellas", ChatFalso([respuesta]))
    assert ficha.categoria == "botellas"
