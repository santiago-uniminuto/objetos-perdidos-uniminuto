-- 0002 · La vista pública expone el código de categoría y el id de zona para filtrar.
-- CREATE OR REPLACE VIEW solo permite AGREGAR columnas al final: las de 0001 quedan iguales.
CREATE OR REPLACE VIEW vista_publica_objetos AS
SELECT 'perdido'::tipo_objeto AS tipo, r.id, r.sede_id, r.creado_en,
       c.nombre AS categoria, z.nombre AS zona, r.descripcion_publica,
       r.fecha_perdida AS fecha, r.estado::text AS estado,
       c.codigo AS categoria_codigo, r.zona_id
FROM reporte_perdida r
JOIN categoria c ON c.id = r.categoria_id
LEFT JOIN zona z ON z.id = r.zona_id
WHERE r.estado IN ('publicado', 'en_coincidencia')
UNION ALL
SELECT 'hallado'::tipo_objeto, h.id, h.sede_id, h.creado_en,
       c.nombre, z.nombre, h.descripcion_publica,
       h.fecha_hallazgo, h.estado::text,
       c.codigo, h.zona_id
FROM hallazgo h
JOIN categoria c ON c.id = h.categoria_id
LEFT JOIN zona z ON z.id = h.zona_id
WHERE h.estado IN ('publicado', 'en_coincidencia');
