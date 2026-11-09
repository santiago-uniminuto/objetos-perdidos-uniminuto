# ADR-003: PostgreSQL es la única fuente de verdad

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** Backend / Datos

## Contexto

El proyecto usa cuatro motores de datos. Si dos guardan "la verdad" de lo mismo, pueden divergir.

## Decisión

Todo dato transaccional (reportes, hallazgos, coincidencias, entregas, consentimientos, auditoría) vive primero en PostgreSQL. MongoDB, Citus y el Data Lake son derivados o guardan datos no transaccionales (atributos, trazas, agregados).

## Consecuencias

- Ante una falla, los derivados se reconstruyen desde PostgreSQL.
- Los backups críticos son los de PostgreSQL.
- Teorema CAP: PostgreSQL se trata como CP; los derivados aceptan consistencia eventual.
