# ADR-020: Coincidencias entre sedes de la misma ciudad

- **Estado:** aceptada
- **Fecha:** 2026-11-14
- **Responsable:** Equipo completo

## Contexto

Cada admin ve y opera solo los reportes y hallazgos de su sede. Pero un estudiante de Calle 80 puede tener una clase en Valmaría y perder algo allá. Si el matcher solo compara objetos de la misma sede, ese caso nunca se encuentra.

En Bogotá hay 7 sedes (6 centros y PCIS). No es razonable que un estudiante tenga clase en otra ciudad, así que el cruce se limita a la ciudad.

El esquema exigía que el reporte y el hallazgo de una coincidencia fueran de la misma sede. Así quedó diseñado para Citus (ADR-012), que reparte los datos por `sede_id`.

## Decisión (aprobada por el equipo)

**Sede de custodia.**
- La coincidencia vive en la sede donde está el objeto: `sede_id` es la sede del hallazgo.
- La sede donde se reportó la pérdida queda en la columna nueva `reporte_sede_id`.
- El matcher busca candidatos en todas las sedes activas de la misma `ciudad`.
- Las zonas son de cada sede, así que entre sedes distintas la zona cuenta como dato desconocido, no como diferencia.

**Quién hace qué.**

| | Sede de custodia (tiene el objeto) | Sede del reporte |
|---|---|---|
| Ve la sugerencia | Sí, completa | Sí, sin el detalle interno, la bodega ni las fotos del hallazgo |
| Verifica / rechaza | Sí | No (403) |
| Datos del dueño | Solo después de verificar, para la entrega (auditado) | Sí, el reporte es suyo |
| Registra la entrega | Sí | No |

El correo al dueño dice a qué sede ir y su dirección.

**Estado al entregar.** El reporte y el hallazgo quedan en `entregado`, antes `cerrado`. Así el filtro "Entregados" los encuentra. La migración corrige los casos ya entregados.

**Contador del analista.** `GET /analitica/resumen` devuelve `ultima_corrida`, `proxima_corrida` y `cada_horas`. Usa la misma regla que el programador de los agentes: la última corrida más `ANALISTA_HORAS`.

## Consecuencias

- **Citus:** la llave `coincidencia → reporte` ahora usa `reporte_sede_id`. Citus solo admite llaves entre tablas distribuidas sobre la misma columna, así que `datos/citus/01-distribuir.sql` la quita antes de distribuir. En Citus esa integridad la garantizan el matcher y la API. Las consultas del matcher y de la bandeja tocan varios fragmentos (las sedes de una ciudad). Es aceptable: son pocas sedes y la búsqueda vectorial ya estaba acotada por categoría y fechas.
- `intento_entrega` pasa a tener llave primaria `(id, sede_id)` y se distribuye junto a `coincidencia`.
- Bajar la migración borra las coincidencias entre sedes, porque no caben en el esquema anterior.
