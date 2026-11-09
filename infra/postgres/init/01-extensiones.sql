-- Se ejecuta solo la primera vez que se crea el volumen de PostgreSQL.
CREATE EXTENSION IF NOT EXISTS vector;     -- embeddings (pgvector)
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- búsqueda aproximada de texto
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid(), hashes
