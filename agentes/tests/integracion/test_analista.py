"""Agente analista contra PostgreSQL real y un lake local con tablas gold de prueba.

    PRUEBAS_INTEGRACION=1 DATABASE_URL=postgresql://... pytest tests/integracion
"""

import json
import os
import time
from datetime import date, timedelta

import mongomock
import psycopg
import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
import pytest
from psycopg.rows import dict_row

from harness.analista import Analista
from harness.lago import LectorGold
from harness.nucleo import RegistroTrazas
from ia.proveedores import Uso

pytestmark = pytest.mark.skipif(
    os.environ.get("PRUEBAS_INTEGRACION") != "1", reason="requiere PostgreSQL (PRUEBAS_INTEGRACION=1)"
)
URL = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:5432/objetos_perdidos")
HOY = date(2026, 11, 10)


class ChatFalso:
    """Primera respuesta con una cifra inventada (debe rechazarse); luego una correcta."""

    modelo = "qwen-falso"

    def __init__(self, respuestas):
        self.respuestas, self.mensajes = list(respuestas), []

    def completar(self, mensajes, json=True, temperatura=0.0, max_tokens=400):
        self.mensajes.append(mensajes)
        return self.respuestas.pop(0), Uso(300, 80, 5.0)


def _escribir(raiz, nombre, filas):
    (raiz / "gold" / nombre).mkdir(parents=True)
    pq.write_table(pa.Table.from_pylist(filas), raiz / "gold" / nombre / "datos.parquet")


@pytest.fixture
def lago(tmp_path):
    lunes = HOY - timedelta(days=HOY.weekday())
    cal, serie = [], []
    for i in range(-40, 8):
        s = lunes + timedelta(days=7 * i)
        n = (i % 20) + 1 if i % 20 < 18 else None
        cal.append({"semana_inicio": s, "semana_semestre": n, "es_parciales": n in (8, 16)})
        if i < 1:  # la semana actual también llega con datos parciales: el analista debe ignorarla
            base = 40 if n is None else (180 if n in (8, 16) else 100)
            serie.append({"sede_id": 1, "semana_inicio": s, "perdidas": base + (i % 3), "hallazgos": base // 2,
                          "semana_semestre": n, "es_parciales": n in (8, 16)})
    _escribir(tmp_path, "calendario", cal)
    _escribir(tmp_path, "serie_semanal", serie)
    _escribir(tmp_path, "kpi_recuperacion_mensual", [
        {"sede_id": 1, "sede": "Sede principal", "categoria": c, "anio": 2026, "mes": m, "reportados": 200,
         "recuperados": r, "tasa": r / 200, "mediana_dias": 3.0}
        for m, c, r in ((9, "Documentos", 150), (9, "Ropa", 70), (10, "Documentos", 140), (10, "Ropa", 60),
                        (11, "Documentos", 10))])
    _escribir(tmp_path, "mapa_calor_zona_hora", [
        {"sede_id": 1, "zona": "Biblioteca", "dia_semana": 2, "franja": "09-12", "perdidas": 90},
        {"sede_id": 1, "zona": "Aulas", "dia_semana": 1, "franja": "sin hora", "perdidas": 500}])
    _escribir(tmp_path, "calidad_matching", [
        {"semana_inicio": lunes - timedelta(days=7), "sugeridas": 50, "aceptadas": 40, "rechazadas": 10,
         "pendientes": 0, "precision": 0.8}])
    return LectorGold(pafs.LocalFileSystem(), str(tmp_path))


@pytest.fixture
def conn():
    c = psycopg.connect(URL, autocommit=True, row_factory=dict_row)
    yield c
    c.close()


def _ultimo(conn, sede):
    return conn.execute("SELECT * FROM informe_analitica WHERE sede_id IS NOT DISTINCT FROM %s "
                        "ORDER BY creado_en DESC LIMIT 1", (sede,)).fetchone()


def test_informe_con_llm_verificado(lago, conn):
    trazas = mongomock.MongoClient().db.trazas_agente
    chat = ChatFalso([
        json.dumps({"resumen": "Se recuperó el 77,7 % de los objetos."}),  # 77,7 no está en los datos
        json.dumps({"resumen": "En octubre se recuperó el 50 % de 400 objetos. Biblioteca los martes de 09-12 "
                               "es el punto crítico. Esta semana se esperan más pérdidas por parciales."}),
    ])
    salida = Analista(RegistroTrazas(trazas), conn, lago, chat, hoy=HOY).correr()
    assert [t["disparador"]["ref"] for t in salida] == ["global", "1"]
    assert all(t["estado"] == "ok" for t in salida[:1])

    inf = _ultimo(conn, None)
    m, p = inf["metricas"], inf["prediccion"]
    assert inf["resumen_fuente"] == "llm" and "77,7" not in inf["resumen"]
    assert m["mes"]["periodo"] == "2026-10" and m["mes"]["reportados"] == 400
    assert m["mes"]["tasa_recuperacion_pct"] == 50.0
    assert m["mes"]["tasa_mes_anterior_pct"] == 55.0
    assert m["mes"]["categoria_menos_recuperada"]["categoria"] == "Ropa"
    assert m["zonas_criticas"][0] == {"zona": "Biblioteca", "dia": "martes", "franja": "09-12", "perdidas": 90}
    assert m["matching_4_semanas"]["precision_pct"] == 80.0
    lunes = HOY - timedelta(days=HOY.weekday())
    assert p["semanas"][0]["semana_inicio"] == lunes.isoformat()  # la semana en curso se predice, no se usa
    assert len(p["semanas"]) == 4 and p["backtest"]["semanas_evaluadas"] == 12

    doc = trazas.find_one({"ejecucion_id": inf["ejecucion_id"]})
    pasos = [x["herramienta"] for x in doc["pasos"]]
    assert pasos == ["leer_gold", "calcular_metricas", "predecir", "redactar_resumen", "verificar_cifras",
                     "redactar_resumen", "guardar_informe"]
    assert doc["llamadas_llm"] == 2
    # El LLM solo recibe agregados: ningún texto libre de reportes ni datos personales
    enviado = chat.mensajes[0][1]["content"]
    assert "descripcion" not in enviado and "correo" not in enviado and "estudiante" not in enviado


def test_llm_que_siempre_inventa_cae_a_plantilla(lago, conn):
    trazas = mongomock.MongoClient().db.trazas_agente
    chat = ChatFalso([json.dumps({"resumen": "Se perdieron 123456 objetos."})] * 4)
    salida = Analista(RegistroTrazas(trazas), conn, lago, chat, hoy=HOY).correr()
    assert salida[0]["estado"] == "respaldo"
    inf = _ultimo(conn, None)
    assert inf["resumen_fuente"] == "plantilla" and inf["modelo_llm"] is None
    assert "400" in inf["resumen"] and "123456" not in inf["resumen"]


def test_sin_llm_ni_datos(tmp_path, conn):
    vacio = LectorGold(pafs.LocalFileSystem(), str(tmp_path))
    assert Analista(RegistroTrazas(None), conn, vacio, None, hoy=HOY).correr() == []


def test_programador_respeta_el_periodo(conn):
    from harness.worker import Programador

    class AnalistaFalso:
        corridas = 0

        def correr(self):
            self.corridas += 1
            return [{"estado": "ok"}]

    falso = AnalistaFalso()
    conn.execute("INSERT INTO informe_analitica (datos_hasta, metricas, prediccion, resumen, resumen_fuente, "
                 "ejecucion_id) VALUES (now(), '{}', '{}', 'x', 'plantilla', 'prueba')")
    assert Programador(conn, falso, horas=6).tick() is False          # hay un informe reciente
    time.sleep(0.05)
    p = Programador(conn, falso, horas=1e-5)                          # 36 ms
    assert p.tick() is True and falso.corridas == 1                   # vencido: corre
    assert p.tick() is False and falso.corridas == 1                  # no revisa de nuevo antes de 5 min
    assert Programador(conn, None, horas=6).tick() is False           # sin lake configurado no hace nada
