# ADR-011: SeaweedFS como almacenamiento S3 del Data Lake (en lugar de MinIO)

- **Estado:** aceptada (reemplaza la elección de MinIO de la Fase 2)
- **Fecha:** 2026-11-08
- **Responsable:** Datos

## Contexto

La Fase 2 eligió MinIO. Al crear el repositorio se verificó que MinIO dejó de publicar imágenes Docker de su edición comunitaria en octubre de 2025 y archivó el repositorio en 2026; `docker pull minio/minio` ya no funciona y las copias que quedan no reciben parches de seguridad.

## Decisión

Usar **SeaweedFS** (`chrislusf/seaweedfs`) con su gateway S3 en el puerto 8333. El código del ETL y DuckDB hablan S3 estándar, así que el cambio solo afecta a `docker-compose.yml`.

## Consecuencias

- Proyecto activo, imagen oficial disponible y con interfaz de administración.
- Un solo proceso (`weed server -s3`) en modo nodo único: ligero para 16 GB.
- Si SeaweedFS diera problemas, Garage y RustFS son alternativas S3 compatibles sin cambiar el código.

## Alternativas consideradas

| Alternativa | Por qué se descartó |
| --- | --- |
| MinIO (quay.io o imágenes de terceros) | Sin mantenimiento ni parches; riesgo de seguridad |
| Garage | Más pasos de configuración inicial (layout, llaves) |
| RustFS | Más joven; se deja como respaldo |
