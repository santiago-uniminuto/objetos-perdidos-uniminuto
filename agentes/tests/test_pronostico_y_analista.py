"""Predicción con estacionalidad académica y verificación de cifras del analista (sin base ni LLM)."""

import random
from datetime import date, timedelta

from harness.analista import cifras_inventadas, plantilla
from ia.pronostico import Semana, backtest, cuantil_poisson, factores, pronosticar


def _serie(semanas: int = 80, semilla: int = 3):
    """Semestres de 18 semanas (parciales en 8 y 16) separados por 8 de vacaciones, ruido de Poisson."""
    rnd, inicio = random.Random(semilla), date(2025, 1, 6)
    hist, y = [], []
    for i in range(semanas):
        pos = i % 26
        n = pos + 1 if pos < 18 else None
        s = Semana(inicio + timedelta(days=7 * i), n, n in (8, 16))
        lam = 100 * {"vacaciones": 0.15, "parciales": 1.8, "inicio": 1.2, "normal": 1.0}[s.clase]
        hist.append(s)
        y.append(sum(1 for _ in range(int(lam * 10)) if rnd.random() < 0.1))  # ~Poisson(lam)
    return hist, y


def test_factores_recuperan_la_estacionalidad():
    hist, y = _serie()
    f = factores(hist, y)
    assert 1.6 < f["parciales"] < 2.0 and 0.1 < f["vacaciones"] < 0.25 and f["normal"] == 1.0


def test_modelo_le_gana_a_la_ingenua_y_avisa_los_parciales():
    hist, y = _serie()
    bt = backtest(hist, y)
    assert bt["gana_modelo"] and bt["mae_modelo"] < bt["mae_ingenuo"]
    futuras = [Semana(hist[-1].inicio + timedelta(days=7), 8, True)]
    p = pronosticar(hist, y, futuras)[0]
    assert p["clase"] == "parciales" and 150 < p["esperado"] < 210
    assert p["minimo_90"] < p["esperado"] < p["maximo_90"]


def test_backtest_necesita_historia():
    hist, y = _serie(semanas=10)
    assert backtest(hist, y) is None


def test_cuantiles_poisson():
    assert cuantil_poisson(0, 0.95) == 0
    assert cuantil_poisson(4, 0.05) == 1 and cuantil_poisson(4, 0.95) == 8   # valores de tabla
    assert cuantil_poisson(1000, 0.05) == 948 and cuantil_poisson(1000, 0.95) == 1052  # aproximación normal


def test_detecta_cifras_inventadas():
    hechos = {"reportados": 5118, "tasa": 50.7, "esperado": 745.8, "semana": "2026-11-09"}
    assert cifras_inventadas("Se reportaron 5.118 objetos, se recuperó el 50,7 % y se esperan unas 746 "
                             "pérdidas la semana del 2026-11-09 en 3 zonas.", hechos) == set()
    assert cifras_inventadas("Se recuperó el 63 % de 9.999 objetos.", hechos) == {63.0, 9999.0}


def test_plantilla_sin_datos_y_con_datos():
    assert "no hay datos" in plantilla({"metricas": {}, "prediccion": {}})
    texto = plantilla({"metricas": {"mes": {"periodo": "2026-10", "reportados": 5118, "tasa_recuperacion_pct": 50.7,
                                            "tasa_mes_anterior_pct": 51.7, "categoria_menos_recuperada": None}},
                       "prediccion": {"semanas": [{"semana_inicio": "2026-11-09", "clase": "parciales",
                                                   "esperado": 745.8, "minimo_90": 701, "maximo_90": 791}],
                                      "backtest": {"gana_modelo": False}}})
    assert "5.118" in texto and "50,7 %" in texto and "parciales" in texto and "cautela" in texto
