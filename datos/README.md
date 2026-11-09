# Datos

**Responsable:** Datos · **Se diseña en:** Fase 3

- `etl/`: worker que lee el `outbox` de PostgreSQL y escribe en MongoDB y en el lake (bronze → silver → gold).
- `sintetico/`: generador de ≥ 1 millón de reportes y hallazgos multi-sede.
- `citus/`: registro de workers, distribución de tablas y clave de partición.
- `consultas/`: consultas DuckDB sobre Parquet para la analítica.
