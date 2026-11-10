"""Reconstruye silver y gold desde bronze con DuckDB (sobre tablas Arrow, sin servidor).

silver: eventos deduplicados y "aplanados" por entidad, conformados con los catálogos.
gold:   agregados que leen el tablero y el agente analista. Nada aquí tiene datos personales.
"""

import os
import tempfile
from datetime import date

import duckdb
import pyarrow as pa

from lago.almacen import Lago
from lago.calendario import tabla_semanas

SQL_EVENTOS = """
CREATE OR REPLACE TABLE eventos AS
SELECT outbox_id, creado_en, agregado, agregado_id, sede_id, tipo_evento, payload
FROM bronze
QUALIFY row_number() OVER (PARTITION BY outbox_id ORDER BY creado_en) = 1;   -- duplicados por reproceso
"""

SQL_SILVER_REPORTES = """
CREATE OR REPLACE TABLE s_reportes AS
WITH r AS (
    SELECT payload->>'id' AS reporte_id, sede_id, CAST(payload->>'categoria_id' AS INTEGER) AS categoria_id,
           CAST(payload->>'zona_id' AS INTEGER) AS zona_id, CAST(payload->>'fecha' AS DATE) AS fecha,
           TRY_CAST(payload->>'hora' AS TIME) AS hora, creado_en
    -- descarta eventos incompletos (sin fecha)
    FROM eventos WHERE tipo_evento = 'reporte.creado' AND payload->>'fecha' IS NOT NULL
), e AS (
    SELECT payload->>'reporte_id' AS reporte_id, min(creado_en) AS entregado_en
    FROM eventos WHERE tipo_evento = 'entrega.registrada' GROUP BY 1
)
SELECT r.*, c.nombre AS categoria, z.nombre AS zona, s.nombre AS sede,
       e.entregado_en IS NOT NULL AS recuperado, e.entregado_en,
       CASE WHEN e.entregado_en IS NOT NULL THEN date_diff('day', r.fecha, CAST(e.entregado_en AS DATE)) END
           AS dias_recuperacion,
       year(r.fecha) AS anio, month(r.fecha) AS mes
FROM r LEFT JOIN e USING (reporte_id)
LEFT JOIN categorias c ON c.id = r.categoria_id
LEFT JOIN zonas z ON z.id = r.zona_id
LEFT JOIN sedes s ON s.id = r.sede_id;
"""

SQL_SILVER_HALLAZGOS = """
CREATE OR REPLACE TABLE s_hallazgos AS
WITH h AS (
    SELECT payload->>'id' AS hallazgo_id, sede_id, CAST(payload->>'categoria_id' AS INTEGER) AS categoria_id,
           CAST(payload->>'zona_id' AS INTEGER) AS zona_id, CAST(payload->>'fecha' AS DATE) AS fecha,
           TRY_CAST(payload->>'hora' AS TIME) AS hora, creado_en
    FROM eventos WHERE tipo_evento = 'hallazgo.creado' AND payload->>'fecha' IS NOT NULL
), e AS (
    SELECT payload->>'hallazgo_id' AS hallazgo_id, min(creado_en) AS entregado_en
    FROM eventos WHERE tipo_evento = 'entrega.registrada' GROUP BY 1
)
SELECT h.*, c.nombre AS categoria, z.nombre AS zona, e.entregado_en IS NOT NULL AS entregado,
       year(h.fecha) AS anio, month(h.fecha) AS mes
FROM h LEFT JOIN e USING (hallazgo_id)
LEFT JOIN categorias c ON c.id = h.categoria_id
LEFT JOIN zonas z ON z.id = h.zona_id;
"""

SQL_SILVER_COINCIDENCIAS = """
CREATE OR REPLACE TABLE s_coincidencias AS
WITH s AS (
    SELECT payload->>'id' AS coincidencia_id, sede_id, CAST(payload->>'puntaje' AS DOUBLE) AS puntaje,
           creado_en AS sugerida_en
    FROM eventos WHERE tipo_evento = 'coincidencia.sugerida'
), d AS (
    SELECT payload->>'id' AS coincidencia_id, arg_max(split_part(tipo_evento, '.', 2), creado_en) AS decision,
           max(creado_en) AS decidida_en
    FROM eventos WHERE tipo_evento IN ('coincidencia.verificada', 'coincidencia.rechazada') GROUP BY 1
), e AS (
    SELECT DISTINCT payload->>'coincidencia_id' AS coincidencia_id FROM eventos
    WHERE tipo_evento = 'entrega.registrada'
)
SELECT s.*, CASE WHEN e.coincidencia_id IS NOT NULL THEN 'entregada' ELSE coalesce(d.decision, 'pendiente') END
           AS estado_final, d.decidida_en
FROM s LEFT JOIN d USING (coincidencia_id) LEFT JOIN e USING (coincidencia_id);
"""

SQL_GOLD = {
    "kpi_recuperacion_mensual": """
        SELECT sede_id, sede, categoria, anio, mes, count(*) AS reportados,
               count(*) FILTER (WHERE recuperado) AS recuperados,
               round(count(*) FILTER (WHERE recuperado) / count(*), 4) AS tasa,
               median(dias_recuperacion) AS mediana_dias
        FROM s_reportes GROUP BY ALL ORDER BY anio, mes, sede_id, categoria""",
    "mapa_calor_zona_hora": """
        SELECT sede_id, coalesce(zona, 'Sin zona') AS zona, isodow(fecha) AS dia_semana,
               CASE WHEN hora IS NULL THEN 'sin hora'
                    WHEN hour(hora) < 9 THEN '06-09' WHEN hour(hora) < 12 THEN '09-12'
                    WHEN hour(hora) < 15 THEN '12-15' WHEN hour(hora) < 18 THEN '15-18' ELSE '18-22' END AS franja,
               count(*) AS perdidas
        FROM s_reportes GROUP BY ALL ORDER BY sede_id, perdidas DESC""",
    "serie_semanal": """
        WITH p AS (SELECT sede_id, date_trunc('week', fecha)::DATE AS semana_inicio, count(*) AS perdidas
                   FROM s_reportes GROUP BY ALL),
             h AS (SELECT sede_id, date_trunc('week', fecha)::DATE AS semana_inicio, count(*) AS hallazgos
                   FROM s_hallazgos GROUP BY ALL)
        SELECT coalesce(p.sede_id, h.sede_id) AS sede_id, coalesce(p.semana_inicio, h.semana_inicio) AS semana_inicio,
               coalesce(perdidas, 0) AS perdidas, coalesce(hallazgos, 0) AS hallazgos,
               cal.semana_semestre, coalesce(cal.es_parciales, false) AS es_parciales
        FROM p FULL JOIN h ON p.sede_id = h.sede_id AND p.semana_inicio = h.semana_inicio
        LEFT JOIN calendario cal ON cal.semana_inicio = coalesce(p.semana_inicio, h.semana_inicio)
        ORDER BY sede_id, semana_inicio""",
    "calidad_matching": """
        SELECT date_trunc('week', sugerida_en)::DATE AS semana_inicio, count(*) AS sugeridas,
               count(*) FILTER (WHERE estado_final IN ('verificada', 'entregada')) AS aceptadas,
               count(*) FILTER (WHERE estado_final = 'rechazada') AS rechazadas,
               count(*) FILTER (WHERE estado_final = 'pendiente') AS pendientes,
               round(count(*) FILTER (WHERE estado_final IN ('verificada', 'entregada'))
                     / nullif(count(*) FILTER (WHERE estado_final <> 'pendiente'), 0), 4) AS precision
        FROM s_coincidencias GROUP BY ALL ORDER BY semana_inicio""",
}


def _arrow(db: duckdb.DuckDBPyConnection, sql: str) -> pa.Table:
    """Resultado como tabla Arrow (DuckDB 2.x: to_arrow_table; 1.x: arrow)."""
    relacion = db.sql(sql)
    return relacion.to_arrow_table() if hasattr(relacion, "to_arrow_table") else relacion.arrow()


def _catalogos(conn) -> dict[str, pa.Table]:
    """Instantánea de los catálogos (sin datos personales) para conformar silver."""
    return {
        "sedes": pa.Table.from_pylist(conn.execute("SELECT id, nombre FROM sede").fetchall()
                                      or [{"id": 0, "nombre": ""}]),
        "zonas": pa.Table.from_pylist(conn.execute("SELECT id, sede_id, nombre FROM zona").fetchall()
                                      or [{"id": 0, "sede_id": 0, "nombre": ""}]),
        "categorias": pa.Table.from_pylist(conn.execute("SELECT id, codigo, nombre FROM categoria").fetchall()
                                           or [{"id": 0, "codigo": "", "nombre": ""}]),
    }


def transformar(lago: Lago, conn) -> dict:
    bronze = lago.dataset("bronze/eventos")
    if bronze is None:
        return {"eventos": 0}
    # Límite de memoria: con 1 M de reportes (~8 M de eventos) DuckDB vuelca a disco en vez de agotar la RAM
    db = duckdb.connect(config={"memory_limit": os.environ.get("DUCKDB_MEMORIA", "2GB"),
                                "temp_directory": os.environ.get("DUCKDB_TEMP", tempfile.gettempdir())})
    db.register("bronze", bronze)
    for nombre, tabla in _catalogos(conn).items():
        db.register(nombre, tabla)
    calendario = pa.Table.from_pylist(tabla_semanas(date(2024, 1, 1), date(2027, 12, 31)))
    db.register("calendario", calendario)

    # db.sql ejecuta y cierra cada sentencia (DuckDB 2.x no deja resultados abiertos entre llamadas)
    db.sql(SQL_EVENTOS)
    for sql in (SQL_SILVER_REPORTES, SQL_SILVER_HALLAZGOS, SQL_SILVER_COINCIDENCIAS):
        db.sql(sql)

    resumen = {"eventos": db.sql("SELECT count(*) FROM eventos").fetchall()[0][0]}
    for tabla, carpeta, particiones in (("s_reportes", "silver/reportes", ["anio", "mes"]),
                                        ("s_hallazgos", "silver/hallazgos", ["anio", "mes"]),
                                        ("s_coincidencias", "silver/coincidencias", None)):
        datos = _arrow(db, f"SELECT * FROM {tabla}")  # noqa: S608 - nombres fijos
        lago.reemplazar(carpeta, datos, particiones)
        resumen[carpeta] = datos.num_rows
    for nombre, sql in SQL_GOLD.items():
        datos = _arrow(db, sql)
        lago.reemplazar(f"gold/{nombre}", datos)
        resumen[f"gold/{nombre}"] = datos.num_rows
    lago.reemplazar("silver/catalogos/categorias", _catalogos(conn)["categorias"])
    # El agente analista necesita saber qué semanas FUTURAS son de parciales o vacaciones
    lago.reemplazar("gold/calendario", calendario)
    return resumen
