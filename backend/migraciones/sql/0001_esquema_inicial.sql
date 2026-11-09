-- =====================================================================
-- 0001 · Esquema inicial · Objetos Perdidos UNIMINUTO
-- PostgreSQL 16 + pgvector. Ver docs/adr y el documento de la Fase 3.
--
-- Convenciones
--   * Tablas de alto volumen particionadas por mes en creado_en.
--   * sede_id va en la llave primaria de las tablas operativas: Citus exige
--     que la columna de distribución forme parte de toda llave única.
--   * Ids UUID (la aplicación genera UUIDv7, ordenados en el tiempo).
-- =====================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------- tipos
CREATE TYPE rol_usuario         AS ENUM ('admin_sede', 'auditor');
CREATE TYPE estado_reporte      AS ENUM ('registrado', 'publicado', 'en_coincidencia', 'entregado', 'cerrado', 'expirado');
CREATE TYPE estado_hallazgo     AS ENUM ('registrado', 'publicado', 'en_coincidencia', 'entregado', 'cerrado', 'donado', 'descartado');
CREATE TYPE estado_coincidencia AS ENUM ('sugerida', 'verificada', 'rechazada', 'entregada');
CREATE TYPE tipo_objeto         AS ENUM ('perdido', 'hallado');
CREATE TYPE accion_auditoria    AS ENUM ('crear', 'leer', 'actualizar', 'anonimizar', 'login', 'login_fallido', 'exportar');

-- ----------------------------------------------------------- catálogos
-- Tablas pequeñas: en Citus serán "tablas de referencia" (copia en cada nodo).
CREATE TABLE sede (
    id          smallint PRIMARY KEY,
    codigo      text NOT NULL UNIQUE,
    nombre      text NOT NULL,
    ciudad      text NOT NULL,
    activa      boolean NOT NULL DEFAULT true
);

CREATE TABLE zona (
    id          integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sede_id     smallint NOT NULL REFERENCES sede (id),
    nombre      text NOT NULL,
    activa      boolean NOT NULL DEFAULT true,
    UNIQUE (sede_id, nombre)
);

CREATE TABLE categoria (
    id            smallint PRIMARY KEY,
    codigo        text NOT NULL UNIQUE,
    nombre        text NOT NULL,
    -- Si es documento de identidad, la foto nunca es pública (ADR-007)
    es_documento  boolean NOT NULL DEFAULT false
);

-- ------------------------------------------------------------ personas
CREATE TABLE usuario (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sede_id            smallint REFERENCES sede (id),          -- NULL = auditor global
    email              text NOT NULL,
    nombre             text NOT NULL,
    hash_contrasena    text NOT NULL,                          -- argon2/bcrypt, nunca texto plano
    rol                rol_usuario NOT NULL,
    activo             boolean NOT NULL DEFAULT true,
    intentos_fallidos  smallint NOT NULL DEFAULT 0,
    bloqueado_hasta    timestamptz,
    creado_en          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT usuario_admin_tiene_sede CHECK (rol <> 'admin_sede' OR sede_id IS NOT NULL)
);
CREATE UNIQUE INDEX usuario_email_uq ON usuario (lower(email));

-- Datos personales del dueño (Ley 1581). Solo visibles al admin y auditados.
CREATE TABLE estudiante (
    id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_documento        text NOT NULL CHECK (tipo_documento IN ('CC', 'TI', 'CE', 'PA', 'PPT')),
    numero_documento      text NOT NULL,
    nombres               text NOT NULL,
    apellidos             text NOT NULL,
    correo_institucional  text,
    telefono              text,
    programa              text,
    anonimizado_en        timestamptz,             -- derecho de supresión (HU-15)
    creado_en             timestamptz NOT NULL DEFAULT now(),
    actualizado_en        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tipo_documento, numero_documento)
);

CREATE TABLE consentimiento (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    estudiante_id    uuid NOT NULL REFERENCES estudiante (id),
    version_aviso    text NOT NULL,                -- versión del aviso de privacidad aceptado
    finalidades      text[] NOT NULL,              -- p. ej. {gestion_objeto, notificacion_correo}
    canal            text NOT NULL DEFAULT 'presencial',
    otorgado_en      timestamptz NOT NULL DEFAULT now(),
    revocado_en      timestamptz,
    registrado_por   uuid NOT NULL REFERENCES usuario (id)
);
CREATE INDEX consentimiento_estudiante_idx ON consentimiento (estudiante_id) WHERE revocado_en IS NULL;

-- ------------------------------------------------- operación (particionada)
CREATE TABLE reporte_perdida (
    id                 uuid NOT NULL DEFAULT gen_random_uuid(),
    sede_id            smallint NOT NULL REFERENCES sede (id),
    creado_en          timestamptz NOT NULL DEFAULT now(),
    estudiante_id      uuid NOT NULL REFERENCES estudiante (id),
    categoria_id       smallint NOT NULL REFERENCES categoria (id),
    zona_id            integer REFERENCES zona (id),      -- NULL = no recuerda dónde
    descripcion        text NOT NULL,                     -- uso interno
    descripcion_publica text NOT NULL,                    -- versión sin datos personales
    detalle_control    text,                              -- dato oculto para la pregunta de control
    fecha_perdida      date NOT NULL,
    hora_aprox         time,
    estado             estado_reporte NOT NULL DEFAULT 'publicado',
    registrado_por     uuid NOT NULL REFERENCES usuario (id),
    actualizado_en     timestamptz NOT NULL DEFAULT now(),
    cerrado_en         timestamptz,
    PRIMARY KEY (id, creado_en, sede_id)
) PARTITION BY RANGE (creado_en);

CREATE TABLE hallazgo (
    id                  uuid NOT NULL DEFAULT gen_random_uuid(),
    sede_id             smallint NOT NULL REFERENCES sede (id),
    creado_en           timestamptz NOT NULL DEFAULT now(),
    categoria_id        smallint NOT NULL REFERENCES categoria (id),
    zona_id             integer REFERENCES zona (id),
    descripcion         text NOT NULL,
    descripcion_publica text NOT NULL,
    fecha_hallazgo      date NOT NULL,
    hora_aprox          time,
    encontrado_por      text,                     -- opcional; dato personal del que entrega
    ubicacion_bodega    text,
    foto_clave          text,                     -- llave del objeto en el lake (S3)
    foto_publica        boolean NOT NULL DEFAULT false,
    estado              estado_hallazgo NOT NULL DEFAULT 'publicado',
    vence_en            date NOT NULL,            -- creado_en + DIAS_CUSTODIA (90)
    registrado_por      uuid NOT NULL REFERENCES usuario (id),
    actualizado_en      timestamptz NOT NULL DEFAULT now(),
    cerrado_en          timestamptz,
    PRIMARY KEY (id, creado_en, sede_id)
) PARTITION BY RANGE (creado_en);

-- Un vector por objeto y por modelo: cambiar de modelo no borra los anteriores (ADR-005).
CREATE TABLE objeto_embedding (
    objeto_tipo         tipo_objeto NOT NULL,
    objeto_id           uuid NOT NULL,
    sede_id             smallint NOT NULL,
    categoria_id        smallint NOT NULL REFERENCES categoria (id),
    modelo              text NOT NULL,
    texto_normalizado   text NOT NULL,           -- lo que se vectorizó (sin datos personales)
    vector              vector(1024) NOT NULL,
    creado_en           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (objeto_tipo, objeto_id, modelo, sede_id)
);

CREATE TABLE coincidencia (
    id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    sede_id              smallint NOT NULL,
    creado_en            timestamptz NOT NULL DEFAULT now(),
    reporte_id           uuid NOT NULL,
    reporte_creado_en    timestamptz NOT NULL,
    hallazgo_id          uuid NOT NULL,
    hallazgo_creado_en   timestamptz NOT NULL,
    similitud            real NOT NULL CHECK (similitud BETWEEN -1 AND 1),   -- coseno (pgvector)
    puntaje              numeric(4, 3) NOT NULL CHECK (puntaje BETWEEN 0 AND 1),
    explicacion          text,                    -- NULL si el LLM no respondió
    modelo_llm           text,
    modelo_embedding     text NOT NULL,
    estado               estado_coincidencia NOT NULL DEFAULT 'sugerida',
    decidido_por         uuid REFERENCES usuario (id),
    decidido_en          timestamptz,
    motivo_rechazo       text,
    PRIMARY KEY (id, sede_id),
    UNIQUE (sede_id, reporte_id, hallazgo_id),
    FOREIGN KEY (reporte_id, reporte_creado_en, sede_id)
        REFERENCES reporte_perdida (id, creado_en, sede_id),
    FOREIGN KEY (hallazgo_id, hallazgo_creado_en, sede_id)
        REFERENCES hallazgo (id, creado_en, sede_id),
    -- La IA nunca decide: verificar o rechazar exige un usuario (AGENTS.md, regla 2)
    CONSTRAINT coincidencia_decision_humana CHECK (
        estado = 'sugerida' OR (decidido_por IS NOT NULL AND decidido_en IS NOT NULL)
    ),
    CONSTRAINT coincidencia_motivo_rechazo CHECK (estado <> 'rechazada' OR motivo_rechazo IS NOT NULL)
);

CREATE TABLE entrega (
    id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    sede_id              smallint NOT NULL,
    creado_en            timestamptz NOT NULL DEFAULT now(),
    coincidencia_id      uuid NOT NULL,
    estudiante_id        uuid NOT NULL REFERENCES estudiante (id),
    metodo_verificacion  text NOT NULL DEFAULT 'carne_y_pregunta_control',
    verificacion_ok      boolean NOT NULL CHECK (verificacion_ok),   -- sin verificación no hay entrega
    numero_acta          text NOT NULL,
    observaciones        text,
    registrado_por       uuid NOT NULL REFERENCES usuario (id),
    PRIMARY KEY (id, sede_id),
    UNIQUE (sede_id, coincidencia_id),
    FOREIGN KEY (coincidencia_id, sede_id) REFERENCES coincidencia (id, sede_id)
);

-- -------------------------------------------------- auditoría y outbox
CREATE TABLE auditoria (
    id           bigint GENERATED ALWAYS AS IDENTITY,
    creado_en    timestamptz NOT NULL DEFAULT now(),
    usuario_id   uuid REFERENCES usuario (id),
    accion       accion_auditoria NOT NULL,
    entidad      text NOT NULL,                  -- p. ej. 'estudiante', 'reporte_perdida'
    entidad_id   uuid,
    sede_id      smallint,
    motivo       text,
    ip           inet,
    detalle      jsonb NOT NULL DEFAULT '{}',    -- nunca datos personales
    PRIMARY KEY (id, creado_en)
) PARTITION BY RANGE (creado_en);

-- Auditoría inmutable (ADR-008): ni la propia aplicación puede editarla o borrarla.
CREATE FUNCTION auditoria_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'La tabla auditoria es solo de insercion (ADR-008)';
END;
$$;
CREATE TRIGGER auditoria_sin_update_delete
    BEFORE UPDATE OR DELETE ON auditoria
    FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();

-- Patrón outbox (ADR-004): se escribe en la misma transacción que el cambio.
CREATE TABLE outbox (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    creado_en     timestamptz NOT NULL DEFAULT now(),
    agregado      text NOT NULL,                 -- 'reporte_perdida', 'hallazgo', ...
    agregado_id   uuid NOT NULL,
    sede_id       smallint,
    tipo_evento   text NOT NULL,                 -- 'reporte.creado', 'coincidencia.verificada', ...
    payload       jsonb NOT NULL,                -- ids y campos del objeto; sin datos personales
    procesado_en  timestamptz
);

-- ------------------------------------------------------ particiones
-- Crea particiones mensuales [desde, hasta). Un job mensual la llama para el mes siguiente.
CREATE FUNCTION crear_particiones_mensuales(tabla text, desde date, hasta date)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    mes date := date_trunc('month', desde)::date;
    creadas integer := 0;
    nombre text;
BEGIN
    WHILE mes < hasta LOOP
        nombre := format('%s_%s', tabla, to_char(mes, 'YYYY_MM'));
        IF to_regclass(nombre) IS NULL THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                nombre, tabla, mes, (mes + interval '1 month')::date
            );
            creadas := creadas + 1;
        END IF;
        mes := (mes + interval '1 month')::date;
    END LOOP;
    RETURN creadas;
END;
$$;

-- 2024-01 a 2027-12 cubre los datos sintéticos (2 años de historia) y la operación real.
SELECT crear_particiones_mensuales('reporte_perdida', '2024-01-01', '2028-01-01');
SELECT crear_particiones_mensuales('hallazgo',        '2024-01-01', '2028-01-01');
SELECT crear_particiones_mensuales('auditoria',       '2024-01-01', '2028-01-01');
-- Red de seguridad: si falta una partición, la fila no se pierde.
CREATE TABLE reporte_perdida_default PARTITION OF reporte_perdida DEFAULT;
CREATE TABLE hallazgo_default        PARTITION OF hallazgo DEFAULT;
CREATE TABLE auditoria_default       PARTITION OF auditoria DEFAULT;

-- ------------------------------------------------------------ índices
-- Compuestos para la bandeja del admin (por sede y estado, lo más reciente primero)
CREATE INDEX reporte_sede_estado_idx  ON reporte_perdida (sede_id, estado, creado_en DESC);
CREATE INDEX hallazgo_sede_estado_idx ON hallazgo (sede_id, estado, creado_en DESC);

-- Parciales para la vista pública: solo lo que se publica, ordenado para paginar por cursor
CREATE INDEX reporte_publico_idx  ON reporte_perdida (sede_id, creado_en DESC, id)
    WHERE estado IN ('publicado', 'en_coincidencia');
CREATE INDEX hallazgo_publico_idx ON hallazgo (sede_id, creado_en DESC, id)
    WHERE estado IN ('publicado', 'en_coincidencia');

-- Parcial para el job de vencimiento (90 días)
CREATE INDEX hallazgo_por_vencer_idx ON hallazgo (vence_en) WHERE estado = 'publicado';

-- Filtros del matcher y búsqueda de texto aproximada
CREATE INDEX reporte_categoria_fecha_idx  ON reporte_perdida (sede_id, categoria_id, fecha_perdida);
CREATE INDEX hallazgo_categoria_fecha_idx ON hallazgo (sede_id, categoria_id, fecha_hallazgo);
CREATE INDEX reporte_estudiante_idx       ON reporte_perdida (estudiante_id);
CREATE INDEX reporte_desc_trgm_idx  ON reporte_perdida USING gin (descripcion_publica gin_trgm_ops);
CREATE INDEX hallazgo_desc_trgm_idx ON hallazgo USING gin (descripcion_publica gin_trgm_ops);

-- Búsqueda vectorial aproximada (HNSW, distancia coseno)
CREATE INDEX objeto_embedding_hnsw_idx ON objeto_embedding USING hnsw (vector vector_cosine_ops);
CREATE INDEX objeto_embedding_filtro_idx ON objeto_embedding (sede_id, objeto_tipo, categoria_id);

-- Bandeja de sugerencias pendientes
CREATE INDEX coincidencia_pendiente_idx ON coincidencia (sede_id, creado_en DESC) WHERE estado = 'sugerida';

-- Outbox: el ETL solo lee lo no procesado
CREATE INDEX outbox_pendiente_idx ON outbox (id) WHERE procesado_en IS NULL;

-- Auditoría por usuario y por entidad
CREATE INDEX auditoria_usuario_idx ON auditoria (usuario_id, creado_en DESC);
CREATE INDEX auditoria_entidad_idx ON auditoria (entidad, entidad_id);

-- ------------------------------------------------------ vista pública
-- Única fuente de la página pública: lista blanca de columnas (ADR-007).
CREATE VIEW vista_publica_objetos AS
SELECT 'perdido'::tipo_objeto AS tipo, r.id, r.sede_id, r.creado_en,
       c.nombre AS categoria, z.nombre AS zona, r.descripcion_publica,
       r.fecha_perdida AS fecha, r.estado::text AS estado
FROM reporte_perdida r
JOIN categoria c ON c.id = r.categoria_id
LEFT JOIN zona z ON z.id = r.zona_id
WHERE r.estado IN ('publicado', 'en_coincidencia')
UNION ALL
SELECT 'hallado'::tipo_objeto, h.id, h.sede_id, h.creado_en,
       c.nombre, z.nombre, h.descripcion_publica,
       h.fecha_hallazgo, h.estado::text
FROM hallazgo h
JOIN categoria c ON c.id = h.categoria_id
LEFT JOIN zona z ON z.id = h.zona_id
WHERE h.estado IN ('publicado', 'en_coincidencia');

-- ----------------------------------------------------- datos semilla
INSERT INTO sede (id, codigo, nombre, ciudad) VALUES
    (1, 'SEDE-01', 'Sede principal', 'Bogotá');   -- ajustar nombre real de la sede

INSERT INTO zona (sede_id, nombre)
SELECT 1, z FROM unnest(ARRAY[
    'Parqueadero', 'Aulas', 'Biblioteca', 'Auditorios', 'Baños', 'Terrazas',
    'Zonas verdes', 'CRAI - zona de descanso', 'Cafeterías', 'Admisiones', 'Sala de profesores'
]) AS z;

INSERT INTO categoria (id, codigo, nombre, es_documento) VALUES
    (1, 'electronicos', 'Electrónicos',      false),
    (2, 'documentos',   'Documentos',        true),
    (3, 'ropa',         'Ropa',              false),
    (4, 'accesorios',   'Accesorios',        false),
    (5, 'utiles',       'Útiles',            false),
    (6, 'llaves',       'Llaves',            false),
    (7, 'botellas',     'Botellas y termos', false),
    (8, 'otros',        'Otros',             false);
