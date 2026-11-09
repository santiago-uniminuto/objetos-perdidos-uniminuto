# Citus 12.1 (PostgreSQL 16) + pgvector: la imagen oficial de Citus no trae pgvector
# y el esquema usa columnas vector(1024).
FROM citusdata/citus:12.1

RUN apt-get update \
 && apt-get install -y --no-install-recommends postgresql-16-pgvector \
 && rm -rf /var/lib/apt/lists/*
