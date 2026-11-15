# PostgreSQL vs. Citus · 2026-11-14

Datos: 300.000 reportes, 286.377 hallazgos, 161.134 coincidencias y 151.377 entregas en cada motor.
Citus: 2 workers, 32 shards por tabla. 40 repeticiones por consulta, con los mismos parámetros en los dos motores.

| Consulta | PostgreSQL p50 / p95 (ms) | Citus p50 / p95 (ms) | Shards que toca en Citus |
|---|---|---|---|
| Portal: últimos 25 objetos de una sede | 0.5 / 5.6 | 6.6 / 18.2 | 1 |
| Portal: una sede filtrada por categoría | 0.6 / 4.6 | 6.5 / 9.8 | 1 |
| Matcher: hallazgos candidatos (sede, categoría, ventana de fechas) | 0.5 / 2.9 | 4.5 / 16.1 | 1 |
| Admin: coincidencias de una sede con su hallazgo (join co-ubicado) | 16.7 / 83.6 | 12.8 / 49.4 | 1 |
| Analítica global: reportes por sede y mes (todas las sedes) | 85.0 / 117.7 | 372.1 / 444.4 | 32 |
| Analítica global: tasa de recuperación por categoría (join de 3 tablas) | 153.8 / 172.7 | 528.2 / 588.9 | 32 |
