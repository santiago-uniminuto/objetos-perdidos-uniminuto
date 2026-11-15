-- =====================================================================
-- 0010 · Índices en las columnas que referencian a otras tablas (hallazgo de la Fase 6)
--
-- PostgreSQL indexa la tabla referenciada, no la que referencia. Sin estos índices, cada fila
-- borrada de reporte_perdida, hallazgo o estudiante obligaba a recorrer completa la tabla
-- coincidencia o entrega para comprobar que nadie la usaba: limpiar 1 M de reportes sintéticos
-- tomaba muchos minutos. También los usa el matcher (pares ya sugeridos) y el detalle del reporte.
-- =====================================================================

CREATE INDEX IF NOT EXISTS coincidencia_reporte_idx  ON coincidencia (reporte_id, reporte_creado_en, reporte_sede_id);
CREATE INDEX IF NOT EXISTS coincidencia_hallazgo_idx ON coincidencia (hallazgo_id, hallazgo_creado_en, sede_id);
CREATE INDEX IF NOT EXISTS entrega_estudiante_idx    ON entrega (estudiante_id);
-- consentimiento ya tenía un índice por estudiante, pero PARCIAL (solo vigentes): la verificación de la
-- llave no puede usarlo. Era el 95 % del tiempo al borrar estudiantes (5,4 ms por fila).
CREATE INDEX IF NOT EXISTS consentimiento_estudiante_todos_idx ON consentimiento (estudiante_id);
