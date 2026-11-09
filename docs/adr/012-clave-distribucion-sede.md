# ADR-012: `sede_id` como clave de distribución en Citus

- **Estado:** aceptada (balance por validar con datos sintéticos en la Fase 6)
- **Fecha:** 2026-11-09
- **Responsable:** Datos

## Contexto

El sistema es multi-sede por diseño. Las consultas más frecuentes y costosas siempre filtran por una sede: el matching compara reportes y hallazgos **de la misma sede**, la bandeja del admin muestra **su sede** y la vista pública se consulta por sede.

## Decisión

Distribuir por hash de `sede_id` las tablas `reporte_perdida`, `hallazgo`, `objeto_embedding`, `coincidencia` y `entrega`, co-ubicadas (mismo grupo de co-localización, 32 shards). Catálogos, usuarios y estudiantes como tablas de referencia. `auditoria` y `outbox` quedan en el coordinador.

## Consecuencias

- Matching, bandeja y vista pública por sede tocan **1 shard de 32**; los joins entre reportes, hallazgos y coincidencias son locales.
- `sede_id` tiene baja cardinalidad y las sedes son de tamaño desigual: riesgo de sedes "calientes". Se mide con `datos/citus/02-balance.sql` y, si una sede concentra demasiado, se aísla con `isolate_tenant_to_new_shard`.
- Consultas globales (analítica nacional) tocan los 32 shards; por eso la analítica se hace en el lake, no en Citus.

## Alternativas consideradas

| Clave | Ventaja | Por qué se descartó |
| --- | --- | --- |
| Hash de `id` | Balance casi perfecto | El matching de una sede consulta los 32 shards y los joins cruzan nodos |
| `estudiante_id` | Agrupa el historial de una persona | Los hallazgos no tienen estudiante; no sirve para el matching |
| `creado_en` (rango) | Bueno para archivar | Todas las escrituras van al shard del mes actual (punto caliente) |
