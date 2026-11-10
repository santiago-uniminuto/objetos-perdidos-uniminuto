# ADR-002: La IA corre en workers asíncronos

- **Estado:** aceptada; la parte de colas (ARQ) la reemplaza ADR-014
- **Fecha:** 2026-11-07
- **Responsable:** IA

## Contexto

Un LLM local tarda varios segundos por respuesta. Registrar un reporte debe tardar menos de 500 ms (RNF-02).

## Decisión

La petición HTTP solo guarda y encola. Los agentes (matcher, notificador, analista) consumen la cola en Redis con ARQ.

## Consecuencias

- El registro es rápido; las sugerencias aparecen después (meta: < 30 s, RNF-04).
- Si la IA falla, el reporte ya está guardado y el trabajo se reintenta.
- Se necesita idempotencia en los trabajos (un reintento no duplica coincidencias).

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| Llamar al LLM dentro de la petición | Latencia alta y fallos visibles al usuario |
| Celery + RabbitMQ | Más piezas y RAM; ARQ usa el Redis que ya existe |
