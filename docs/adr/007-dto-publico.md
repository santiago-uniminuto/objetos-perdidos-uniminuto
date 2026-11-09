# ADR-007: Vista pública con DTO propio y lista blanca de campos

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** Backend / Frontend

## Contexto

La página pública no puede mostrar datos personales del dueño ni fotos de documentos de identidad.

## Decisión

Los endpoints `/publico/*` usan modelos de respuesta propios que solo incluyen: tipo (perdido/hallado), categoría, descripción general, zona, fecha y estado. Nunca se reutilizan los modelos internos.

## Consecuencias

- Una prueba falla si una respuesta pública contiene un campo fuera de la lista blanca.
- Las fotos de hallazgos de categoría "documentos" nunca se publican.
