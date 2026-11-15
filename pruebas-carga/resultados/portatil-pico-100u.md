# Prueba de carga · portatil-pico-100u

Escenario: capacidad, 100 usuarios sin pausas, 2 min, 1 M de reportes, portátil 16 GB (Docker Desktop, Caddy delante de la API). Estadísticas reiniciadas al terminar la rampa (`--reset-stats`).
Total: 34.191 peticiones · **296.2 peticiones/s** · errores 0.00% · p95 global 430 ms
Capacidad (RNF-03, meta ≥ 200 peticiones/s): **cumple**. La latencia es de cola por saturación deliberada (ley de Little: 100 usuarios / 300 peticiones/s ≈ 0,33 s) y se reporta solo como dato.

| Ruta | Peticiones | Peticiones/s | p50 (ms) | p95 (ms) | p99 (ms) | Errores |
|---|---:|---:|---:|---:|---:|---:|
| publico: listar | 16902 | 146.4 | 310 | 410 | 510 | 0 |
| publico: detalle | 5629 | 48.8 | 350 | 450 | 540 | 0 |
| publico: página 2 | 4166 | 36.1 | 310 | 420 | 530 | 0 |
| catálogos | 2796 | 24.2 | 340 | 440 | 540 | 0 |
| admin: reportes | 1589 | 13.8 | 350 | 450 | 540 | 0 |
| admin: hallazgos | 1192 | 10.3 | 350 | 460 | 540 | 0 |
| admin: coincidencias | 1158 | 10.0 | 360 | 460 | 540 | 0 |
| admin: registrar reporte | 365 | 3.2 | 400 | 510 | 590 | 0 |
| admin: analítica | 361 | 3.1 | 330 | 430 | 510 | 0 |
| admin: consentimiento | 11 | 0.1 | 430 | 620 | 620 | 0 |
| admin: crear estudiante | 11 | 0.1 | 410 | 480 | 480 | 0 |
| auth: login | 11 | 0.1 | 2800 | 3000 | 3000 | 0 |

Línea de tiempo (`stats_history`): el ritmo sube de 96 a ~300 peticiones/s en los primeros 15 s (calentamiento de la caché) y se mantiene entre 280 y 320 hasta el final, sin congelamientos. La misma prueba antes del PR #27 (cupos) daba 88 peticiones/s, 0,18 % de errores y peticiones de 30 y 60 s.
