# Prueba de carga · sandbox-pico-50u

Escenario: Capacidad: 50 usuarios sin pausas, 90 s, 300 mil reportes, caché pública de 30 s; Locust, API y PostgreSQL comparten 2 CPU
Total: 30.511 peticiones · **342.6 peticiones/s** · errores 0.00% · p95 global 230 ms
Lectura pública (RNF-01, meta p95 < 300 ms): peor ruta 250 ms → **cumple**

| Ruta | Peticiones | Peticiones/s | p50 (ms) | p95 (ms) | p99 (ms) | Errores |
|---|---:|---:|---:|---:|---:|---:|
| publico: listar | 15318 | 172.0 | 120 | 190 | 250 | 0 |
| publico: detalle | 5145 | 57.8 | 170 | 250 | 310 | 0 |
| publico: página 2 | 3763 | 42.3 | 120 | 200 | 260 | 0 |
| catálogos | 2505 | 28.1 | 130 | 200 | 240 | 0 |
| admin: reportes | 1263 | 14.2 | 160 | 230 | 280 | 0 |
| admin: coincidencias | 972 | 10.9 | 210 | 340 | 420 | 0 |
| admin: hallazgos | 899 | 10.1 | 160 | 240 | 290 | 0 |
| admin: registrar reporte | 320 | 3.6 | 200 | 300 | 340 | 0 |
| admin: analítica | 302 | 3.4 | 110 | 170 | 200 | 0 |
| admin: consentimiento | 8 | 0.1 | 670 | 1100 | 1100 | 0 |
| admin: crear estudiante | 8 | 0.1 | 710 | 1100 | 1100 | 0 |
| auth: login | 8 | 0.1 | 1400 | 2400 | 2400 | 0 |
