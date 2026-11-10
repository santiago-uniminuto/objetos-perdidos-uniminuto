"""Generador sintético → outbox → ETL (bronze + Mongo) → silver/gold, contra PostgreSQL real.

Lake en carpeta temporal y Mongo con mongomock.
    PRUEBAS_INTEGRACION=1 DATABASE_URL=postgresql://... pytest tests/integracion
"""

import os
from datetime import date

import mongomock
import psycopg
import pyarrow.fs as pafs
import pytest
from psycopg.rows import dict_row

from lago.almacen import Lago
from lago.etl import procesar_lote
from lago.transformar import transformar
from sintetico.generar import generar, limpiar

pytestmark = pytest.mark.skipif(
    os.environ.get("PRUEBAS_INTEGRACION") != "1", reason="requiere PostgreSQL (PRUEBAS_INTEGRACION=1)"
)
URL = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:5432/objetos_perdidos")
N = 400
CAMPOS_PERSONALES = {"estudiante_id", "nombres", "apellidos", "correo_institucional", "numero_documento",
                     "descripcion", "telefono"}


@pytest.fixture(scope="module")
def entorno(tmp_path_factory):
    with psycopg.connect(URL) as conn:
        limpiar(conn)
        resumen = generar(conn, N, n_sedes=3, desde=date(2025, 7, 1), hasta=date(2025, 12, 31), semilla=91)
    conn = psycopg.connect(URL, autocommit=True, row_factory=dict_row)
    conn.execute("UPDATE consumidor_outbox SET ultimo_id = 0 WHERE consumidor = 'etl'")
    lago = Lago(pafs.LocalFileSystem(), str(tmp_path_factory.mktemp("lago")))
    mongo = mongomock.MongoClient().db.eventos
    mongo.create_index("outbox_id", unique=True)
    yield conn, lago, mongo, resumen
    with psycopg.connect(URL) as c:
        limpiar(c)
    conn.close()


def test_generador_respeta_integridad(entorno):
    conn, _, _, resumen = entorno
    assert resumen["reportes"] == N and resumen["entregas"] <= N
    malas = conn.execute(
        "SELECT count(*) FILTER (WHERE e.creado_en < c.creado_en) AS entrega_antes,"
        "       count(*) FILTER (WHERE c.creado_en < c.reporte_creado_en OR c.creado_en < c.hallazgo_creado_en)"
        "       AS coincidencia_antes FROM entrega e JOIN coincidencia c ON c.id = e.coincidencia_id"
        " WHERE e.numero_acta LIKE 'SIN-%'").fetchone()
    assert malas == {"entrega_antes": 0, "coincidencia_antes": 0}
    # Los agentes no deben procesar lo sintético: su offset quedó al final del outbox
    fin = conn.execute("SELECT max(id) AS m FROM outbox").fetchone()["m"]
    offsets = conn.execute("SELECT consumidor, ultimo_id FROM consumidor_outbox "
                           "WHERE consumidor IN ('matcher', 'notificador')").fetchall()
    assert all(o["ultimo_id"] >= fin for o in offsets)
    # Ningún evento del outbox lleva datos personales
    con_pii = conn.execute("SELECT count(*) AS n FROM outbox WHERE payload ?| %s",
                           (list(CAMPOS_PERSONALES),)).fetchone()["n"]
    assert con_pii == 0


def test_etl_y_transformacion(entorno):
    conn, lago, mongo, resumen = entorno
    total = 0
    while n := procesar_lote(conn, lago, mongo, limite=500):
        total += n
    assert total >= resumen["eventos"]
    assert mongo.count_documents({}) == total

    # Reprocesar un lote (como tras una caída) no duplica nada en Mongo ni en silver
    conn.execute("UPDATE consumidor_outbox SET ultimo_id = ultimo_id - 300 WHERE consumidor = 'etl'")
    assert procesar_lote(conn, lago, mongo, limite=300) == 300
    assert mongo.count_documents({}) == total

    lago.compactar("bronze/eventos", max_partes=1)
    r = transformar(lago, conn)
    assert r["eventos"] == total  # duplicados de bronze descartados por outbox_id

    reportes = lago.leer("silver/reportes")
    sinteticos = conn.execute("SELECT count(*) AS n FROM reporte_perdida WHERE descripcion LIKE '%(sintético)'"
                              ).fetchone()["n"]
    assert reportes.num_rows >= sinteticos == N
    tasa = sum(reportes["recuperado"].to_pylist()) / reportes.num_rows
    assert 0.3 < tasa < 0.8  # tasas por categoría entre 0.30 y 0.72

    for carpeta in ("silver/reportes", "silver/hallazgos", "silver/coincidencias", "gold/kpi_recuperacion_mensual",
                    "gold/mapa_calor_zona_hora", "gold/serie_semanal", "gold/calidad_matching", "gold/calendario"):
        tabla = lago.leer(carpeta)
        assert tabla is not None and tabla.num_rows > 0, carpeta
        assert not CAMPOS_PERSONALES & set(tabla.column_names), carpeta

    calidad = lago.leer("gold/calidad_matching").to_pylist()
    rechazadas = sum(f["rechazadas"] for f in calidad)
    aceptadas = sum(f["aceptadas"] for f in calidad)
    assert rechazadas > 0 and aceptadas > rechazadas
