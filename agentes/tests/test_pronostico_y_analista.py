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
    assert "octubre de 2026" in texto and "9 al 15 de noviembre" in texto
    assert "5.118" in texto and "50,7 %" in texto and "parciales" in texto and "cautela" in texto


def test_decimal_pequeno_inventado_y_cifras_faltantes():
    from harness.analista import cifras_faltantes

    hechos = {"tasa": 50.7, "anterior": 51.7}
    assert cifras_inventadas("La recuperación bajó 1,0 % frente al mes anterior.", hechos) == {1.0}  # resta del LLM
    assert cifras_faltantes("Se recuperó el 50,7 % y se esperan 2.093 pérdidas.", [50.7, 2093]) == []
    assert cifras_faltantes("Todo va bien.", [50.7, 2093]) == [50.7, 2093]
    # El rango completo también vale como cifra clave (lo que hace qwen2.5:3b en la práctica)
    clave = (2093, (2018, 2169))
    assert cifras_faltantes("Se espera una pérdida de entre 2.018 y 2.169 objetos.", [clave]) == []
    assert cifras_faltantes("Se esperan más de 2.018 objetos.", [clave]) == [clave]


def test_hechos_para_redactar_en_lenguaje_llano():
    from harness.analista import hechos_para_redactar

    h = {"sede": "Todas las sedes",
         "metricas": {"mes": {"periodo": "2026-10", "reportados": 5118, "recuperados": 2594,
                              "tasa_recuperacion_pct": 50.7, "tasa_mes_anterior_pct": 51.7}},
         "prediccion": {"semanas": [{"semana_inicio": "2026-11-09", "clase": "parciales", "esperado": 2093.2,
                                     "minimo_90": 2018, "maximo_90": 2169},
                                    {"semana_inicio": "2026-11-30", "clase": "vacaciones", "esperado": 167.3,
                                     "minimo_90": 146, "maximo_90": 189}],
                        "backtest": {"gana_modelo": False}}}
    r, reglas = hechos_para_redactar(h, date(2026, 11, 10))
    assert r["recuperacion"]["mes"] == "octubre de 2026"
    assert r["recuperacion"]["cambio_frente_al_mes_anterior"] == "bajó 1,0 puntos"   # el LLM no resta
    assert r["recuperacion"]["frase"] == "De 5.118 objetos reportados en octubre de 2026 se recuperaron 2.594 (50,7 %)"
    assert r["prediccion"][0]["frase"] == ("Esta semana (9 al 15 de noviembre) es semana de parciales y se esperan "
                                           "unas 2.093 pérdidas, entre 2.018 y 2.169")
    assert r["prediccion"][1]["cuando"] == "dentro de tres semanas"
    assert r["prediccion"][1]["fechas"] == "30 de noviembre al 6 de diciembre"
    assert r["confiabilidad_de_la_prediccion"].startswith("baja")
    assert reglas == {"cifras": [50.7, (2093, (2018, 2169))], "palabras": ["parciales"],
                      "atribuciones": {5118: "report", 2594: "recuper"}}


def test_detecta_reportados_presentados_como_recuperados():
    from harness.analista import mal_atribuidas

    reglas = {5118: "report", 2594: "recuper"}
    # Error real de qwen2.5:3b en el portátil
    assert mal_atribuidas("En octubre de 2026, se recuperaron 5118 objetos, lo que representa un 50.7% del total "
                          "de objetos reportados.", reglas) == [5118]
    assert mal_atribuidas("De 5.118 objetos reportados se recuperaron 2.594.", reglas) == []
    assert mal_atribuidas("Se reportaron 5118 objetos y se recuperó el 50,7 %.", reglas) == []
    # La palabra puede estar lejos del número si es la misma cláusula
    assert mal_atribuidas("De los 5.118 objetos perdidos que la comunidad reportó en octubre, se recuperaron 2.594.",
                          reglas) == []
    assert mal_atribuidas("Se reportaron 5.118 objetos y 2.594 fueron entregados.", reglas) == [2594]
