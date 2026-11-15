-- =====================================================================
-- 0009 · Índices para el listado del admin (hallazgo de la Fase 6)
--
-- El panel lista "lo más reciente de mi sede" (ORDER BY creado_en DESC, id DESC) sin filtrar
-- por estado. Ningún índice cubría ese orden: con 300 mil reportes, la sede principal leía y
-- ordenaba ~100 mil filas por petición (p50 180 ms). Con este índice, y como las tablas están
-- particionadas por mes, PostgreSQL recorre solo las particiones más recientes (Merge Append + LIMIT).
-- =====================================================================

CREATE INDEX IF NOT EXISTS reporte_sede_reciente_idx ON reporte_perdida (sede_id, creado_en DESC, id DESC);
CREATE INDEX IF NOT EXISTS hallazgo_sede_reciente_idx ON hallazgo (sede_id, creado_en DESC, id DESC);
