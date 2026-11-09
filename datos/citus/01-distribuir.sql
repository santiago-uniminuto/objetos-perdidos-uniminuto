-- =====================================================================
-- Citus · distribución del esquema (perfil "escala")
-- Ejecutar en el COORDINADOR después de aplicar el esquema 0001:
--   ver datos/citus/README.md
--
-- Clave de distribución: sede_id (justificación en la Fase 3 y en ADR-012).
--   * reporte_perdida, hallazgo, objeto_embedding, coincidencia y entrega
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

-- 2. Tablas de referencia (en orden de dependencias) ---------------------
SELECT create_reference_table('sede');
SELECT create_reference_table('categoria');
SELECT create_reference_table('zona');
SELECT create_reference_table('usuario');
SELECT create_reference_table('estudiante');
SELECT create_reference_table('consentimiento');

-- 3. Tablas distribuidas por sede_id, co-ubicadas ------------------------
SET citus.shard_count = 32;   -- 16 shards por worker; permite crecer a más workers
SELECT create_distributed_table('reporte_perdida',  'sede_id');
SELECT create_distributed_table('hallazgo',         'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('objeto_embedding', 'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('coincidencia',     'sede_id', colocate_with => 'reporte_perdida');
SELECT create_distributed_table('entrega',          'sede_id', colocate_with => 'reporte_perdida');

-- 4. Verificación -------------------------------------------------------
SELECT * FROM citus_get_active_worker_nodes();
SELECT table_name, citus_table_type, distribution_column, colocation_id, shard_count
FROM citus_tables ORDER BY citus_table_type, table_name;
