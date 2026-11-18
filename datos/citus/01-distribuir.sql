-- =====================================================================
-- Citus · distribución del esquema (perfil "escala")
-- Ejecutar en el COORDINADOR después de aplicar TODAS las migraciones (alembic upgrade head):
--   ver datos/citus/README.md. Validado en la Fase 6 con Citus 12.1.6 + PostgreSQL 16.
--
-- Clave de distribución: sede_id (justificación en la Fase 3 y en ADR-012).
--   * reporte_perdida, hallazgo, objeto_embedding, coincidencia, entrega, intento_entrega y
--     consecutivo_acta
--     quedan CO-UBICADAS: las filas de una sede viven en el mismo shard,
--     así el matching y la bandeja del admin se resuelven en un solo nodo.
--   * Catálogos y personas son tablas de REFERENCIA: copia completa en cada nodo.
--   * auditoria y outbox se quedan en el coordinador (no se distribuyen).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS citus;

-- 1. Nodos -------------------------------------------------------------
SELECT citus_set_coordinator_host('citus-coordinador', 5432);
SELECT citus_add_node('citus-worker-1', 5432);
SELECT citus_add_node('citus-worker-2', 5432);
-- pgvector no se instala a mano en los workers: Citus copia las extensiones del coordinador al
-- agregar cada nodo (verificado en la Fase 6). La imagen ya trae el paquete (infra/citus/Dockerfile).

-- 2. Tablas de referencia (en orden de dependencias) ---------------------
SELECT create_reference_table('sede');
SELECT create_reference_table('categoria');
SELECT create_reference_table('zona');
SELECT create_reference_table('usuario');
SELECT create_reference_table('estudiante');
SELECT create_reference_table('consentimiento');

-- 3. Tablas distribuidas por sede_id, co-ubicadas ------------------------
-- ADR-020: una coincidencia puede unir un reporte de una sede con un hallazgo de otra sede de la
-- misma ciudad. La llave coincidencia -> reporte usa reporte_sede_id, y Citus solo admite llaves
-- entre tablas distribuidas que usen la MISMA columna de distribución. Se quita aquí; la integridad
-- la garantizan el matcher y la API (solo insertan pares que existen).
ALTER TABLE coincidencia DROP CONSTRAINT IF EXISTS coincidencia_reporte_fk;

-- Citus no distribuye una tabla mientras otra tabla LOCAL tenga una llave hacia ella (ni al revés).
-- Las llaves entre las tablas que se van a distribuir se quitan aquí y se vuelven a crear en el
-- paso 4, ya entre tablas distribuidas y co-ubicadas (todas incluyen sede_id, así que Citus las acepta).
ALTER TABLE coincidencia    DROP CONSTRAINT coincidencia_hallazgo_id_hallazgo_creado_en_sede_id_fkey;
ALTER TABLE entrega         DROP CONSTRAINT entrega_coincidencia_id_sede_id_fkey;
ALTER TABLE intento_entrega DROP CONSTRAINT intento_entrega_coincidencia_id_sede_id_fkey;

SET citus.shard_count = 32;   -- 16 shards por worker; permite crecer a más workers
SELECT create_distributed_table('reporte_perdida',  'sede_id');
SELECT create_distributed_table('hallazgo',         'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('objeto_embedding', 'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('coincidencia',     'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('entrega',          'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('intento_entrega',  'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('consecutivo_acta', 'sede_id', colocate_with => 'reporte_perdida');

-- 4. Llaves entre tablas distribuidas (co-ubicadas por sede_id) ---------
ALTER TABLE coincidencia ADD CONSTRAINT coincidencia_hallazgo_id_hallazgo_creado_en_sede_id_fkey
    FOREIGN KEY (hallazgo_id, hallazgo_creado_en, sede_id) REFERENCES hallazgo (id, creado_en, sede_id);
ALTER TABLE entrega ADD CONSTRAINT entrega_coincidencia_id_sede_id_fkey
    FOREIGN KEY (coincidencia_id, sede_id) REFERENCES coincidencia (id, sede_id);
ALTER TABLE intento_entrega ADD CONSTRAINT intento_entrega_coincidencia_id_sede_id_fkey
    FOREIGN KEY (coincidencia_id, sede_id) REFERENCES coincidencia (id, sede_id);

-- 5. Vista pública ------------------------------------------------------
-- Al distribuir reporte_perdida, Citus borra y vuelve a crear (solo en el coordinador) las vistas que
-- dependen de ella. Si el script se interrumpe a mitad, pueden quedar borradas: esto las garantiza.
-- vista_publica_fotos se crea pero no se puede consultar: une fotos (tabla local) con reportes
-- (distribuida), y eso Citus no lo admite (ver README, "Hallazgos").
CREATE OR REPLACE VIEW vista_publica_objetos AS
SELECT 'perdido'::tipo_objeto AS tipo, r.id, r.sede_id, r.creado_en,
       c.nombre AS categoria, z.nombre AS zona, r.descripcion_publica,
       r.fecha_perdida AS fecha, r.estado::text AS estado,
       c.codigo AS categoria_codigo, r.zona_id
FROM reporte_perdida r
JOIN categoria c ON c.id = r.categoria_id
LEFT JOIN zona z ON z.id = r.zona_id
WHERE r.estado IN ('publicado', 'en_coincidencia');

-- 6. Verificación -------------------------------------------------------
SELECT * FROM citus_get_active_worker_nodes();
SELECT table_name, citus_table_type, distribution_column, colocation_id, shard_count
FROM citus_tables ORDER BY citus_table_type, table_name;
