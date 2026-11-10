-- 0005 · Portal público solo con objetos PERDIDOS y restablecimiento de contraseña (Fase 5, parte 4)

-- 1. Decisión del equipo (ADR-016): los objetos HALLADOS ya no se publican. Si se publica "celular
--    negro encontrado en Biblioteca", aparecen muchos supuestos dueños. Se publica lo que la
--    comunidad PERDIÓ, para que quien lo encuentre lo lleve a la oficina; el cruce con lo hallado lo
--    hace el matcher en privado y el admin verifica al dueño con la pregunta de control.
--    Se conservan las columnas (incluida `tipo`) para no romper a los clientes de la API.
DROP VIEW vista_publica_objetos;
CREATE VIEW vista_publica_objetos AS
SELECT 'perdido'::tipo_objeto AS tipo, r.id, r.sede_id, r.creado_en,
       c.nombre AS categoria, z.nombre AS zona, r.descripcion_publica,
       r.fecha_perdida AS fecha, r.estado::text AS estado,
       c.codigo AS categoria_codigo, r.zona_id
FROM reporte_perdida r
JOIN categoria c ON c.id = r.categoria_id
LEFT JOIN zona z ON z.id = r.zona_id
WHERE r.estado IN ('publicado', 'en_coincidencia');

-- 2. Enlaces de restablecimiento: se guarda el SHA-256 del token, nunca el token (si alguien lee la
--    tabla no puede usar los enlaces). Un solo uso, vencen a los 30 minutos.
CREATE TABLE restablecimiento_contrasena (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id   uuid NOT NULL REFERENCES usuario (id),
    token_hash   bytea NOT NULL UNIQUE,
    creado_en    timestamptz NOT NULL DEFAULT now(),
    vence_en     timestamptz NOT NULL,
    usado_en     timestamptz,
    origen       text NOT NULL CHECK (origen IN ('correo', 'consola'))
);
CREATE INDEX restablecimiento_usuario_idx ON restablecimiento_contrasena (usuario_id) WHERE usado_en IS NULL;

ALTER TYPE accion_auditoria ADD VALUE IF NOT EXISTS 'cambio_contrasena';
ALTER TYPE accion_auditoria ADD VALUE IF NOT EXISTS 'solicitud_restablecimiento';
