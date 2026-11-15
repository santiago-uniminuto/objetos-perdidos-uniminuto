# ADR-021: Resultados de la Fase 6 (carga y Citus)

- **Estado:** aceptada
- **Fecha:** 2026-11-14
- **Responsable:** Equipo completo

## Contexto

La Fase 6 debía comprobar RNF-01 (p95 de la lectura pública < 300 ms con ≥ 1 M de reportes) y RNF-03 (≥ 200 peticiones/s con caché), y validar el clúster Citus de ADR-012 con datos sintéticos.

Se escribió un escenario de Locust (`pruebas-carga/`) y un comparador PostgreSQL vs. Citus (`datos/citus/comparar.py`). Citus 12.1.6 se compiló desde el código fuente para validarlo de verdad en el entorno de desarrollo (2 CPU, 300 mil reportes).

## Decisiones

1. **Cupos asíncronos antes de pedir conexión (`DB_POOL_MAX` − 2 cupos).** Bajo pico, la API se congelaba hasta el `PoolTimeout` (30 s). FastAPI saca la conexión en un hilo y ejecuta la ruta en otro: todos los hilos podían quedar esperando conexión mientras todas las conexiones esperaban hilo. Igualar hilos y conexiones, la primera corrección, solo lo hacía menos probable; en el portátil volvió a aparecer. Con cupos, esperar uno no ocupa hilo ni conexión, y quien tiene cupo siempre encuentra conexión. Resultado: 150 usuarios sin pausa pasaron de 7,4 a 368,6 peticiones/s, con 0 errores.
2. **Índices `(sede_id, creado_en DESC, id DESC)` en reportes y hallazgos** (migración 0009). Con ellos, el listado del admin bajó de un p50 de 180 ms a 11 ms. Con las tablas particionadas por mes, PostgreSQL lee solo las particiones recientes.
3. **El portal no pide conexión a PostgreSQL si la respuesta está en Redis.** Con caché caliente, la lectura pública no compite por el pool.
4. **Índices en las columnas de las llaves foráneas** (migración 0010): `coincidencia.reporte_id`, `coincidencia.hallazgo_id`, `entrega.estudiante_id`, y uno completo en `consentimiento.estudiante_id`. El que había era parcial y la verificación de la llave no lo usaba. Borrar 2,4 M de filas sintéticas pasó de más de 20 minutos a 45 s. Regla para el resto del proyecto: toda llave foránea lleva un índice no parcial en la tabla que referencia.
5. **El login no retiene nada mientras calcula argon2.** Antes bloqueaba la fila del usuario y calculaba argon2 con la fila, la conexión y el hilo tomados, así que una ráfaga de logins (o un atacante con contraseñas erradas) congelaba la API. Ahora: lectura sin bloqueo, argon2 con su propio límite (la mitad de los núcleos, sin ocupar los hilos de la API) y contadores actualizados en una sentencia atómica, que mantiene el bloqueo tras 5 fallos.
6. **Citus queda como copia de escala y analítica, no como base de la API.** El esquema completo se distribuye y el generador carga sin cambios, pero 15 consultas de la API usan joins que Citus no soporta (fotos locales, cruces entre sedes de ADR-020, `FOR UPDATE` entre sedes). Detalle en `datos/citus/README.md`. Adaptarlas no aporta nada en un solo portátil, donde Citus es más lento por diseño (salto coordinador → worker y 32 tareas sobre 2 CPU).

## Resultados oficiales (portátil, 1 M de reportes)

- RNF-01: p95 de la lectura pública 18–22 ms con 200 usuarios con pausas reales, 0 errores.
- RNF-03: 296 peticiones/s sostenidas con 100 usuarios sin pausas, 0 errores.

## Consecuencias

- La tabla de resultados del artículo sale del portátil con 1 M de reportes (`pruebas-carga/README.md`). Los números del entorno de desarrollo quedan como referencia.
- Para producción con varias máquinas, el paso siguiente sería distribuir `foto_objeto` y resolver los cruces entre sedes en dos consultas. Así cada consulta de la API toca un solo shard.
- La meta "≥ 1 M de reportes" de RNF-01 se valida en el portátil; en desarrollo se usaron 300 mil por límite de CPU y disco.
