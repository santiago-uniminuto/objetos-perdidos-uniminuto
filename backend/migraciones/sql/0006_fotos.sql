-- 0006 · Fotos de los objetos (Fase 5, parte 4b · ADR-018)

-- Hasta 3 fotos por objeto. El archivo vive en SeaweedFS (bucket de fotos), en dos tamaños WebP
-- sin metadatos; aquí solo queda la ficha. Reglas de visibilidad en la vista pública de abajo.
CREATE TABLE foto_objeto (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sede_id       smallint NOT NULL REFERENCES sede (id),
    objeto_tipo   tipo_objeto NOT NULL,                 -- 'perdido' (reporte) | 'hallado' (hallazgo)
    objeto_id     uuid NOT NULL,                        -- sin FK: las tablas de objetos están particionadas
    orden         smallint NOT NULL CHECK (orden BETWEEN 1 AND 3),
    clave         text NOT NULL,                        -- prefijo en el bucket: <clave>/grande.webp y mini.webp
    ancho         integer NOT NULL,
    alto          integer NOT NULL,
    bytes         integer NOT NULL,
    sha256        bytea NOT NULL,                       -- del archivo original: evita subir la misma foto dos veces
    subido_por    uuid NOT NULL REFERENCES usuario (id),
    creado_en     timestamptz NOT NULL DEFAULT now(),
    UNIQUE (objeto_tipo, objeto_id, orden),
    UNIQUE (objeto_tipo, objeto_id, sha256)
);
CREATE INDEX foto_objeto_objeto_idx ON foto_objeto (objeto_tipo, objeto_id);

-- Qué fotos puede ver el público: solo de reportes de PÉRDIDA publicados (ADR-016) y nunca de la
-- categoría documentos (una foto de un carné o una cédula es un dato personal).
CREATE VIEW vista_publica_fotos AS
SELECT f.id, f.objeto_id, f.orden, f.clave, f.ancho, f.alto
FROM foto_objeto f
JOIN reporte_perdida r ON r.id = f.objeto_id
JOIN categoria c ON c.id = r.categoria_id
WHERE f.objeto_tipo = 'perdido'
  AND r.estado IN ('publicado', 'en_coincidencia')
  AND NOT c.es_documento;
