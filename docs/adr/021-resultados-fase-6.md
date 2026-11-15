# ADR-021: Resultados de la Fase 6 (carga y Citus)

- **Estado:** aceptada
- **Fecha:** 2026-11-14
- **Responsable:** Equipo completo

## Contexto

La Fase 6 debía comprobar RNF-01 (p95 de la lectura pública < 300 ms con ≥ 1 M de reportes) y RNF-03 (≥ 200 peticiones/s con caché), y validar el clúster Citus de ADR-012 con datos sintéticos.

Se escribió un escenario de Locust (`pruebas-carga/`) y un comparador PostgreSQL vs. Citus (`datos/citus/comparar.py`). Citus 12.1.6 se compiló desde el código fuente para validarlo de verdad en el entorno de desarrollo (2 CPU, 300 mil reportes).

## Decisiones

1. **Hilos de la API = conexiones del pool (`DB_POOL_MAX`, 20).** Bajo pico, la API se congelaba 30 s: 40 hilos esperaban conexión entre 10 conexiones, y quien tenía una no conseguía hilo para devolverla. Al igualar los dos límites el interbloqueo no puede ocurrir. Resultado: 343 peticiones/s durante 90 s, 0 errores.
2. **Índices `(sede_id, creado_en DESC, id DESC)` en reportes y hallazgos** (migración 0009). Con ellos, el listado del admin bajó de un p50 de 180 ms a 11 ms. Con las tablas particionadas por mes, PostgreSQL lee solo las particiones recientes.
3. **El portal no pide conexión a PostgreSQL si la respuesta está en Redis.** Con caché caliente, la lectura pública no compite por el pool.
4. **Citus queda como copia de escala y analítica, no como base de la API.** El esquema completo se distribuye y el generador carga sin cambios, pero 15 consultas de la API usan joins que Citus no soporta (fotos locales, cruces entre sedes de ADR-020, `FOR UPDATE` entre sedes). Detalle en `datos/citus/README.md`. Adaptarlas no aporta nada en un solo portátil, donde Citus es más lento por diseño (salto coordinador → worker y 32 tareas sobre 2 CPU).

## Consecuencias

- La tabla de resultados del artículo sale del portátil con 1 M de reportes (`pruebas-carga/README.md`). Los números del entorno de desarrollo quedan como referencia.
- Para producción con varias máquinas, el paso siguiente sería distribuir `foto_objeto` y resolver los cruces entre sedes en dos consultas. Así cada consulta de la API toca un solo shard.
- La meta "≥ 1 M de reportes" de RNF-01 se valida en el portátil; en desarrollo se usaron 300 mil por límite de CPU y disco.
