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
