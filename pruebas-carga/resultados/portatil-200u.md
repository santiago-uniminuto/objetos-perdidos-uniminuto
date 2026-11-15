# Prueba de carga · portatil-200u

Escenario: 200 usuarios con pausas reales, 5 min, 1 M de reportes, portátil 16 GB (Docker Desktop, Caddy delante de la API). Estadísticas reiniciadas al terminar la rampa (`--reset-stats`).
Total: 25.047 peticiones · **86.5 peticiones/s** · errores 0.00% · p95 global 22 ms
Lectura pública (RNF-01, meta p95 < 300 ms): peor ruta 22 ms → **cumple**

| Ruta | Peticiones | Peticiones/s | p50 (ms) | p95 (ms) | p99 (ms) | Errores |
|---|---:|---:|---:|---:|---:|---:|
| publico: listar | 13229 | 45.7 | 7 | 18 | 34 | 0 |
| publico: detalle | 4245 | 14.7 | 8 | 17 | 26 | 0 |
| publico: página 2 | 3299 | 11.4 | 6 | 22 | 38 | 0 |
| catálogos | 2087 | 7.2 | 9 | 20 | 48 | 0 |
| admin: reportes | 682 | 2.4 | 12 | 19 | 28 | 0 |
| admin: coincidencias | 550 | 1.9 | 25 | 38 | 53 | 0 |
| admin: hallazgos | 537 | 1.9 | 12 | 21 | 39 | 0 |
| admin: analítica | 200 | 0.7 | 8 | 15 | 21 | 0 |
| admin: registrar reporte | 191 | 0.7 | 13 | 24 | 35 | 0 |
| admin: consentimiento | 9 | 0.0 | 15 | 25 | 25 | 0 |
| admin: crear estudiante | 9 | 0.0 | 18 | 100 | 100 | 0 |
| auth: login | 9 | 0.0 | 2300 | 2400 | 2400 | 0 |

Línea de tiempo (`stats_history`): el máximo (2,4 s) se fija en el primer segundo después del reinicio de estadísticas, con peticiones que empezaron durante la rampa (API recién iniciada, admins calculando argon2), y no vuelve a subir en los 5 minutos.
