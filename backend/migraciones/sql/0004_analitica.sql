-- 0004 · Informes del agente analista (Fase 5, parte 3c)

-- Un informe por corrida y sede (sede_id NULL = todas las sedes). Solo agregados: sin datos personales.
-- `metricas` y `prediccion` son los números calculados en código; `resumen` es el texto que redacta el
-- LLM a partir de esos números (o una plantilla fija si el LLM falla o inventa cifras).
CREATE TABLE informe_analitica (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sede_id          smallint REFERENCES sede (id),
    creado_en        timestamptz NOT NULL DEFAULT now(),
    datos_hasta      date NOT NULL,                       -- última semana con datos en gold
    metricas         jsonb NOT NULL,
    prediccion       jsonb NOT NULL,
    resumen          text NOT NULL,
    resumen_fuente   text NOT NULL CHECK (resumen_fuente IN ('llm', 'plantilla')),
    modelo_llm       text,
    ejecucion_id     text NOT NULL                        -- traza en Mongo (trazas_agente)
);
CREATE INDEX informe_analitica_ultimo_idx ON informe_analitica (sede_id, creado_en DESC);
