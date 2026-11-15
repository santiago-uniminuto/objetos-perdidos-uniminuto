# Prueba de carga · sandbox-100u

Escenario: 100 usuarios con pausas reales (85 % portal, 15 % admin), 2 min, 300 mil reportes, máquina de desarrollo de 2 CPU
Total: 5.061 peticiones · **42.5 peticiones/s** · errores 0.00% · p95 global 26 ms
Lectura pública (RNF-01, meta p95 < 300 ms): peor ruta 26 ms → **cumple**

| Ruta | Peticiones | Peticiones/s | p50 (ms) | p95 (ms) | p99 (ms) | Errores |
|---|---:|---:|---:|---:|---:|---:|
| publico: listar | 2613 | 21.9 | 6 | 24 | 69 | 0 |
| publico: detalle | 875 | 7.3 | 9 | 20 | 27 | 0 |
| publico: página 2 | 655 | 5.5 | 6 | 26 | 37 | 0 |
| catálogos | 434 | 3.6 | 7 | 17 | 52 | 0 |
| admin: reportes | 146 | 1.2 | 12 | 21 | 24 | 0 |
| admin: hallazgos | 119 | 1.0 | 11 | 24 | 30 | 0 |
| admin: coincidencias | 105 | 0.9 | 30 | 45 | 56 | 0 |
| admin: registrar reporte | 38 | 0.3 | 11 | 22 | 29 | 0 |
| admin: analítica | 31 | 0.3 | 5 | 8 | 10 | 0 |
| admin: consentimiento | 15 | 0.1 | 9 | 16 | 16 | 0 |
| admin: crear estudiante | 15 | 0.1 | 10 | 160 | 160 | 0 |
| auth: login | 15 | 0.1 | 200 | 430 | 430 | 0 |
