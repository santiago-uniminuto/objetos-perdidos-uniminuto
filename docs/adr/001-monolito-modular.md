# ADR-001: Monolito modular + workers

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** Backend

## Contexto

Equipo de 4 personas y un solo portátil de 16 GB como servidor. El sistema tiene dominios claros (reportes, hallazgos, matching, entregas, público, auditoría, analítica) pero poco tráfico real.

## Decisión

Una sola API FastAPI organizada en módulos (`backend/app/modulos/<dominio>`) y procesos *worker* aparte para IA y ETL.

## Consecuencias

- Un solo despliegue y una sola base de código para la API.
- Regla: un módulo no lee tablas de otro; se comunican por funciones de servicio.
- Si algún día se necesitara, un módulo puede extraerse como servicio sin rediseñar.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| Microservicios | Más red, despliegues y fallos parciales sin beneficio a esta escala; más RAM |
