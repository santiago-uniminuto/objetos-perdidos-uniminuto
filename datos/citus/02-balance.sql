-- Balance de datos entre workers (Fase 6). Ejecutar en el coordinador después de cargar datos sintéticos.

-- 1. Tamaño por worker. reporte_perdida está particionada por mes: los datos viven en las particiones
--    (reporte_perdida_2025_03, ...), no en la tabla padre, por eso se suman todas.
SELECT nodename || ':' || nodeport AS worker, count(*) AS shards, pg_size_pretty(sum(shard_size)) AS tamano
FROM citus_shards
WHERE table_name::text LIKE 'reporte_perdida%'
GROUP BY 1 ORDER BY 1;

-- 2. Sedes más cargadas y en qué worker vive cada una (ley de Zipf: la sede principal pesa más).
--    Primero se cuenta en los workers; el nodo de cada sede se busca después, sobre ese resultado.
WITH por_sede AS (SELECT sede_id, count(*) AS reportes FROM reporte_perdida GROUP BY sede_id)
SELECT p.sede_id, p.reportes, n.nodename || ':' || n.nodeport AS worker
FROM por_sede p
JOIN pg_dist_placement pl ON pl.shardid = get_shard_id_for_distribution_column('reporte_perdida', p.sede_id)
JOIN pg_dist_node n ON n.groupid = pl.groupid
ORDER BY p.reportes DESC LIMIT 12;

-- 3. ¿Una consulta de una sede toca un solo shard? (debe decir "Task Count: 1")
EXPLAIN (COSTS OFF)
SELECT h.id FROM hallazgo h WHERE h.sede_id = 1 AND h.categoria_id = 7 AND h.estado = 'publicado';

-- 4. Una consulta global se reparte en todos los shards ("Task Count: 32")
EXPLAIN (COSTS OFF)
SELECT sede_id, count(*) FROM reporte_perdida GROUP BY sede_id;

-- Mitigación si una sede concentra demasiadas filas: aislarla en su propio shard
-- SELECT isolate_tenant_to_new_shard('reporte_perdida', 1, cascade_option => 'CASCADE');
