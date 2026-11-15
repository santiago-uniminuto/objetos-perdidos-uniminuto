-- Borra lo que crea la prueba de carga (perfil AdminSede): reportes "(carga)" y sus estudiantes sintéticos.
-- Uso: Get-Content pruebas-carga/limpiar.sql | docker compose exec -T postgres psql -U app -d objetos_perdidos
BEGIN;
-- Los agentes saltan al final del outbox: no mandan al LLM los reportes de la prueba
UPDATE consumidor_outbox SET ultimo_id = (SELECT coalesce(max(id), 0) FROM outbox)
WHERE consumidor IN ('matcher', 'notificador');

DELETE FROM intento_entrega i USING coincidencia c, reporte_perdida r
WHERE i.coincidencia_id = c.id AND c.reporte_id = r.id AND r.descripcion = 'Objeto de prueba de carga (carga)';
DELETE FROM entrega e USING coincidencia c, reporte_perdida r
WHERE e.coincidencia_id = c.id AND c.reporte_id = r.id AND r.descripcion = 'Objeto de prueba de carga (carga)';
DELETE FROM coincidencia c USING reporte_perdida r
WHERE c.reporte_id = r.id AND r.descripcion = 'Objeto de prueba de carga (carga)';
DELETE FROM reporte_perdida WHERE descripcion = 'Objeto de prueba de carga (carga)';
DELETE FROM consentimiento WHERE estudiante_id IN
    (SELECT id FROM estudiante WHERE nombres = 'Carga' AND apellidos = 'Sintética');
DELETE FROM estudiante e WHERE e.nombres = 'Carga' AND e.apellidos = 'Sintética'
    AND NOT EXISTS (SELECT 1 FROM reporte_perdida r WHERE r.estudiante_id = e.id);
COMMIT;
