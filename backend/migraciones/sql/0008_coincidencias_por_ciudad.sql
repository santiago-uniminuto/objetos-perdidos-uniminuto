-- =====================================================================
-- 0008 · Coincidencias entre sedes de la misma ciudad (ADR-020)
--
-- Un estudiante de Calle 80 puede perder algo en una clase en Valmaría.
-- La coincidencia vive en la sede de CUSTODIA (sede_id = sede del hallazgo,
-- donde está el objeto y donde se entrega). La sede donde se reportó la
-- pérdida queda en reporte_sede_id: su admin la ve, pero no decide.
--
-- Además: al entregar, el reporte y el hallazgo quedan en 'entregado'
-- (antes 'cerrado'), para que el filtro "Entregados" los encuentre.
-- =====================================================================

ALTER TABLE coincidencia ADD COLUMN reporte_sede_id smallint;
UPDATE coincidencia SET reporte_sede_id = sede_id;
ALTER TABLE coincidencia ALTER COLUMN reporte_sede_id SET NOT NULL;
ALTER TABLE coincidencia ADD CONSTRAINT coincidencia_reporte_sede_fk
    FOREIGN KEY (reporte_sede_id) REFERENCES sede (id);

-- La llave hacia el reporte ahora usa la sede del REPORTE.
-- (Citus no admite esta llave entre fragmentos distintos: ver datos/citus/01-distribuir.sql)
ALTER TABLE coincidencia DROP CONSTRAINT coincidencia_reporte_id_reporte_creado_en_sede_id_fkey;
ALTER TABLE coincidencia ADD CONSTRAINT coincidencia_reporte_fk
    FOREIGN KEY (reporte_id, reporte_creado_en, reporte_sede_id)
    REFERENCES reporte_perdida (id, creado_en, sede_id);

-- Bandeja del admin de la sede del reporte ("solo ver")
CREATE INDEX coincidencia_reporte_sede_idx ON coincidencia (reporte_sede_id, estado);

-- Casos ya entregados: 'cerrado' -> 'entregado'
UPDATE reporte_perdida r SET estado = 'entregado'
WHERE r.estado = 'cerrado'
  AND EXISTS (SELECT 1 FROM coincidencia c WHERE c.reporte_id = r.id AND c.estado = 'entregada');
UPDATE hallazgo h SET estado = 'entregado'
WHERE h.estado = 'cerrado'
  AND EXISTS (SELECT 1 FROM coincidencia c WHERE c.hallazgo_id = h.id AND c.estado = 'entregada');

-- intento_entrega cuelga de coincidencia: en Citus debe distribuirse por sede_id junto a ella,
-- y para eso la llave primaria tiene que incluir la columna de distribución.
ALTER TABLE intento_entrega DROP CONSTRAINT intento_entrega_pkey;
ALTER TABLE intento_entrega ADD PRIMARY KEY (id, sede_id);
