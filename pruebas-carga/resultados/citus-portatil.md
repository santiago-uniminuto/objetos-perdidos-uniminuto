# PostgreSQL vs. Citus · portátil, 1 M de reportes (2026-11-15)

Datos: 1.000.000 de reportes, 953.199 hallazgos, 535.467 coincidencias y 503.199 entregas (8,1 M de filas) en cada motor. El PostgreSQL tenía además 826 reportes de la prueba de carga (0,08 %).
Citus 12.1: coordinador y 2 workers en Docker Desktop, en el mismo portátil de 16 GB; 32 shards por tabla. 30 repeticiones por consulta, con los mismos parámetros en los dos motores.

| Consulta | PostgreSQL p50 / p95 (ms) | Citus p50 / p95 (ms) | Shards que toca en Citus |
|---|---|---|---|
| Portal: últimos 25 objetos de una sede | 1.1 / 25.8 | 10.2 / 265.6 | 1 |
| Portal: una sede filtrada por categoría | 5.8 / 64.7 | 8.6 / 15.5 | 1 |
| Matcher: hallazgos candidatos (sede, categoría, ventana de fechas) | 5.7 / 9.6 | 11.1 / 35.3 | 1 |
| Admin: coincidencias de una sede con su hallazgo (join co-ubicado) | 127.9 / 227.6 | 32.3 / 170.0 | 1 |
| Analítica global: reportes por sede y mes (todas las sedes) | 104.9 / 128.7 | 252.0 / 334.0 | 32 |
| Analítica global: tasa de recuperación por categoría (join de 3 tablas) | 593.0 / 795.7 | 518.7 / 760.4 | 32 |

## Balance entre workers (`02-balance.sql`)

| Worker | Shards (con particiones) | Tamaño de `reporte_perdida` |
|---|---:|---:|
| citus-worker-1 | 800 | 341 MB |
| citus-worker-2 | 800 | 278 MB |

| Sede | Reportes | Worker |
|---:|---:|---|
| 1 | 354.953 (35,5 %) | citus-worker-2 |
| 2 | 165.912 | citus-worker-1 |
| 3 | 106.098 | citus-worker-2 |
| 4 a 12 | 23.366 a 77.193 cada una | citus-worker-1 |

Planes: una consulta de una sede toca 1 shard en 1 worker (`Task Count: 1`, sede 1 en `citus-worker-2`). La analítica global reparte 32 tareas (`Task Count: 32`).

## Lectura

- **Gana Citus** en el join co-ubicado de la bandeja (p50 4× menor: 32 contra 128 ms) y en la analítica pesada de 3 tablas. Cada shard es pequeño y el trabajo se reparte entre los workers.
- **Gana PostgreSQL** en las consultas mínimas de una sede (1 a 6 ms), donde el salto coordinador → worker pesa más que la consulta, y en el conteo global simple, donde coordinar 32 tareas cuesta más que contar.
- **Sede caliente:** la sede principal concentra el 35,5 % de los reportes (distribución de Zipf del generador). Mitigación prevista: `isolate_tenant_to_new_shard` (comentada en `02-balance.sql`).
- **Todo corre en un solo portátil:** los "nodos" comparten CPU, RAM y disco. Con workers en máquinas distintas, la ventaja de Citus en joins por sede y analítica crecería, porque cada sede usaría los recursos de su nodo.
