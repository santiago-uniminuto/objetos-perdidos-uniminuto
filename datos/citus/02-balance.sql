-- Balance de datos entre workers (se usa en la Fase 6 con 1M+ filas sintéticas).

-- Tamaño y filas por worker
SELECT nodename, count(*) AS shards, pg_size_pretty(sum(shard_size)) AS tamano
FROM citus_shards
WHERE table_name = 'reporte_perdida'::regclass
GROUP BY nodename ORDER BY nodename;

-- Filas por sede (detecta sedes "calientes")
SELECT sede_id, count(*) AS reportes
FROM reporte_perdida GROUP BY sede_id ORDER BY reportes DESC LIMIT 10;

-- ¿Una consulta de matching toca un solo shard? (debe decir "Task Count: 1")
EXPLAIN SELECT h.id
FROM hallazgo h
WHERE h.sede_id = 1 AND h.categoria_id = 7 AND h.estado = 'publicado';

-- Mitigación si una sede concentra demasiadas filas: aislarla en su propio shard
-- SELECT isolate_tenant_to_new_shard('reporte_perdida', 1, cascade_option => 'CASCADE');
