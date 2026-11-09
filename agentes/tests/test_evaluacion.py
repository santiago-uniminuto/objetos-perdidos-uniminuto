"""La evaluación funciona de punta a punta con un vectorizador de juguete (sin modelo).

Los números de estas pruebas NO miden la calidad real: eso se hace con bge-m3 en el portátil.
"""

import hashlib
import math
import re

from evaluacion.evaluar import evaluar
from evaluacion.generar_dataset import generar


def vectorizador_juguete(textos, dim=256):
    """Bolsa de trigramas de caracteres con hashing: suficiente para probar el circuito."""
    vectores = []
    for t in textos:
        v = [0.0] * dim
        plano = re.sub(r"\s+", " ", t.lower())
        for i in range(len(plano) - 2):
            h = int(hashlib.md5(plano[i : i + 3].encode(), usedforsecurity=False).hexdigest(), 16)
            v[h % dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        vectores.append([x / n for x in v])
    return vectores


def test_dataset_reproducible_y_bien_formado():
    a, b = generar(50, 30, semilla=3), generar(50, 30, semilla=3)
    assert a == b
    ids_h = {h["id"] for h in a["hallazgos"]}
    assert all(r["hallazgo_correcto"] in ids_h for r in a["reportes"])
    assert sum(h["distractor"] for h in a["hallazgos"]) == 30


def test_evaluacion_crudo_y_heuristica():
    datos = generar(80, 60, semilla=11)
    crudo = evaluar(datos, "crudo", vectorizador_juguete)
    heur = evaluar(datos, "heuristica", vectorizador_juguete)
    for r in (crudo, heur):
        assert 0 <= r["recall@1"] <= r["recall@5"] <= 1
        assert r["fuga_datos_personales"] == 0.0     # el anonimizador no deja pasar nada
    assert heur["precision_umbral"] is not None


class ChatEco:
    """LLM simulado: devuelve la ficha heurística como JSON y cuenta las llamadas."""

    modelo = "eco"

    def __init__(self):
        self.llamadas = 0

    def completar(self, mensajes, **_):
        from ia.normalizador import heuristica
        from ia.proveedores import Uso

        self.llamadas += 1
        texto = mensajes[-1]["content"].split("<descripcion>\n")[1].split("\n</descripcion>")[0]
        categoria = mensajes[-1]["content"].split(": ")[1].split("\n")[0]
        return heuristica(texto, categoria).model_dump_json(), Uso(1, 1, 1.0)


def test_llm_usa_cache_y_entrega_barrido_de_umbral():
    datos = generar(20, 10, semilla=5)
    chat, cache = ChatEco(), {}
    r1 = evaluar(datos, "llm", vectorizador_juguete, chat, cache=cache)
    llamadas = chat.llamadas
    r2 = evaluar(datos, "llm", vectorizador_juguete, chat, cache=cache)
    assert llamadas == 50 and chat.llamadas == llamadas      # 20 reportes + 30 hallazgos; la 2.ª vez, 0 llamadas
    assert r1["recall@5"] == r2["recall@5"]
    assert r1["json_invalido_tras_reintento"] == 0.0
    barrido = r1["barrido_umbral"]
    assert [f["umbral"] for f in barrido] == sorted(f["umbral"] for f in barrido)
    # subir el umbral nunca aumenta las sugerencias
    sugerencias = [f["sugerencias_por_reporte"] for f in barrido]
    assert sugerencias == sorted(sugerencias, reverse=True)
