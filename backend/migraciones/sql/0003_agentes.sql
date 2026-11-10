-- 0003 · Soporte para los agentes (ADR-014)

-- Cada consumidor del outbox (matcher, notificador, ETL) guarda el último evento que procesó.
-- El outbox funciona como cola durable: si un worker se cae, retoma desde su último id.
CREATE TABLE consumidor_outbox (
    consumidor      text PRIMARY KEY,
    ultimo_id       bigint NOT NULL DEFAULT 0,
    actualizado_en  timestamptz NOT NULL DEFAULT now()
);
INSERT INTO consumidor_outbox (consumidor) VALUES ('matcher'), ('notificador'), ('etl');

-- La ficha normalizada (JSON validado) junto al vector: el puntaje compara atributos
-- (colores, marca, tipo) sin volver a llamar al LLM.
ALTER TABLE objeto_embedding ADD COLUMN ficha jsonb NOT NULL DEFAULT '{}';

-- Búsqueda de candidatos: vecinos del tipo opuesto, misma sede y categoría, mismo modelo
CREATE INDEX objeto_embedding_candidatos_idx ON objeto_embedding (sede_id, categoria_id, objeto_tipo, modelo);
