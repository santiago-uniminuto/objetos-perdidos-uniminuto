# ADR-004: Patrón outbox como CDC

- **Estado:** aceptada
- **Fecha:** 2026-11-07
- **Responsable:** Datos

## Contexto

Los cambios en PostgreSQL deben llegar a MongoDB y al Data Lake sin perderse, aunque un servicio esté caído.

## Decisión

Cada operación de negocio inserta un evento en la tabla `outbox` **en la misma transacción**. Un worker ETL lee el outbox en orden, publica en Mongo y escribe Parquet en la capa bronze, y marca el evento como procesado.

## Consecuencias

- Garantía "al menos una vez": los consumidores deben ser idempotentes (clave = id del evento).
- Ahorra ~2 GB de RAM frente a Debezium + Kafka.
- Es CDC a nivel de aplicación; en el artículo se compara con CDC por log (WAL).

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| Debezium + Kafka | Demasiada RAM para un portátil de 16 GB |
| Doble escritura desde la API | Si una escritura falla, los motores divergen |
