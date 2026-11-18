-- 0011 · Actas de entrega numeradas por el sistema y acta firmada en el registro
--
-- El número del acta ya no lo escribe el admin: sale de un consecutivo por sede y año
-- (ACTA-<código de sede>-<año>-<00001>), así no hay números repetidos ni inventados.
-- El admin imprime el acta, la firman quien entrega y quien recibe, y sube una foto del
-- acta firmada. Esa foto tiene datos personales: solo la ve el admin de la sede y no entra
-- en la retención de 90 días de las fotos de objetos (es el soporte legal de la entrega).

CREATE TABLE consecutivo_acta (
    sede_id  smallint NOT NULL REFERENCES sede (id),
    anio     smallint NOT NULL,
    ultimo   integer  NOT NULL CHECK (ultimo > 0),
    PRIMARY KEY (sede_id, anio)
);

ALTER TABLE entrega ADD COLUMN acta_clave text;
ALTER TABLE entrega ADD COLUMN acta_subida_en timestamptz;
ALTER TABLE entrega ADD COLUMN acta_subida_por uuid REFERENCES usuario (id);

-- Las actas que numera el sistema no se repiten en una sede (las antiguas, escritas a mano, quedan igual
-- aunque tengan números repetidos)
CREATE UNIQUE INDEX entrega_numero_acta_idx ON entrega (sede_id, numero_acta) WHERE numero_acta ~ '^ACTA-[A-Z0-9-]+-[0-9]{4}-[0-9]{5}$';
