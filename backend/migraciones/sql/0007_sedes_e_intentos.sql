-- 0007 · Sedes reales de UNIMINUTO e intentos de entrega fallidos

-- 1. Sedes (ADR-019). En el sistema, una "sede" es un CENTRO UNIVERSITARIO con oficina de objetos
--    perdidos; `region` es la sede institucional que lo agrupa (Acuerdo 412: 6 regionales + PCIS).
--    UNIMINUTO Virtual queda fuera: no tiene espacio físico donde se pierdan cosas.
--    Fuente: directorio institucional "Encuentra tu sede" y centros universitarios de Bogotá (nov. 2026).
ALTER TABLE sede ADD COLUMN region text NOT NULL DEFAULT 'Sin región';
ALTER TABLE sede ADD COLUMN direccion text;

INSERT INTO sede (id, codigo, nombre, ciudad, region, direccion) VALUES
    (1, 'BOG-CALLE80', 'Calle 80 - Minuto de Dios (Sede Principal)', 'Bogotá', 'Bogotá-Cundinamarca-Boyacá', 'Cra. 73A # 81B-70, Engativá'),
    (2, 'U-VALMARIA', 'Valmaría', 'Bogotá', 'Bogotá-Cundinamarca-Boyacá', 'Calle 119 # 4-22, Usaquén'),
    (3, 'U-CALLE-170', 'Calle 170', 'Bogotá', 'Bogotá-Cundinamarca-Boyacá', 'Calle 170 # 8G-31, Usaquén'),
    (4, 'U-SAN-CAMILO', 'San Camilo', 'Bogotá', 'Bogotá-Cundinamarca-Boyacá', 'Calle 1 # 9-50, Santa Fe'),
    (5, 'U-SAN-LUCAS', 'San Lucas', 'Bogotá', 'Bogotá-Cundinamarca-Boyacá', 'Calle 35A Sur # 78I-21, Kennedy'),
    (6, 'U-PERDOMO-PADRE-RAFA', 'Perdomo - Padre Rafael García Herreros', 'Bogotá', 'Bogotá-Cundinamarca-Boyacá', 'Cra. 72 # 57R-41, Ciudad Bolívar'),
    (7, 'U-PARQUE-CIENTIFICO', 'Parque Científico de Innovación Social (PCIS)', 'Bogotá', 'Nacional', 'Sector Calle 90'),
    (8, 'U-GIRARDOT', 'Girardot', 'Girardot', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (9, 'U-MADRID', 'Madrid', 'Madrid', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (10, 'U-SOACHA', 'Soacha', 'Soacha', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (11, 'U-ZIPAQUIRA', 'Zipaquirá', 'Zipaquirá', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (12, 'U-VILLETA', 'Villeta', 'Villeta', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (13, 'U-LA-MESA', 'La Mesa', 'La Mesa', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (14, 'U-UBATE', 'Ubaté', 'Ubaté', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (15, 'U-FACATATIVA', 'Facatativá', 'Facatativá', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (16, 'U-FUNZA', 'Funza', 'Funza', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (17, 'U-FUSAGASUGA', 'Fusagasugá', 'Fusagasugá', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (18, 'U-CHIQUINQUIRA', 'Chiquinquirá', 'Chiquinquirá', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (19, 'U-DUITAMA', 'Duitama', 'Duitama', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (20, 'U-PUERTO-BOYACA', 'Puerto Boyacá', 'Puerto Boyacá', 'Bogotá-Cundinamarca-Boyacá', NULL),
    (21, 'U-BELLO', 'Bello', 'Bello', 'Antioquia-Chocó', NULL),
    (22, 'U-APARTADO', 'Apartadó', 'Apartadó', 'Antioquia-Chocó', NULL),
    (23, 'U-URABA', 'Urabá', 'Urabá', 'Antioquia-Chocó', NULL),
    (24, 'U-ITAGUI-ABURRA-SUR', 'Itagüí (Aburrá Sur)', 'Itagüí', 'Antioquia-Chocó', NULL),
    (25, 'U-EL-BAGRE', 'El Bagre', 'El Bagre', 'Antioquia-Chocó', NULL),
    (26, 'U-RIONEGRO', 'Rionegro', 'Rionegro', 'Antioquia-Chocó', NULL),
    (27, 'U-QUIBDO', 'Quibdó', 'Quibdó', 'Antioquia-Chocó', NULL),
    (28, 'U-CAUCASIA', 'Caucasia', 'Caucasia', 'Antioquia-Chocó', NULL),
    (29, 'U-ZARAGOZA', 'Zaragoza', 'Zaragoza', 'Antioquia-Chocó', NULL),
    (30, 'U-BARRANQUILLA', 'Barranquilla', 'Barranquilla', 'Caribe', NULL),
    (31, 'U-CARTAGENA', 'Cartagena', 'Cartagena', 'Caribe', NULL),
    (32, 'U-SANTA-MARTA', 'Santa Marta', 'Santa Marta', 'Caribe', NULL),
    (33, 'U-MAGANGUE', 'Magangué', 'Magangué', 'Caribe', NULL),
    (34, 'U-GUARANDA', 'Guaranda', 'Guaranda', 'Caribe', NULL),
    (35, 'U-CALI', 'Cali', 'Cali', 'Centro Occidente', NULL),
    (36, 'U-BUENAVENTURA', 'Buenaventura', 'Buenaventura', 'Centro Occidente', NULL),
    (37, 'U-YUMBO', 'Yumbo', 'Yumbo', 'Centro Occidente', NULL),
    (38, 'U-BUGA', 'Buga', 'Buga', 'Centro Occidente', NULL),
    (39, 'U-CARTAGO', 'Cartago', 'Cartago', 'Centro Occidente', NULL),
    (40, 'U-MIRANDA', 'Miranda', 'Miranda', 'Centro Occidente', NULL),
    (41, 'U-PASTO', 'Pasto', 'Pasto', 'Centro Occidente', NULL),
    (42, 'U-IPIALES', 'Ipiales', 'Ipiales', 'Centro Occidente', NULL),
    (43, 'U-GUAITARILLA', 'Guaitarilla', 'Guaitarilla', 'Centro Occidente', NULL),
    (44, 'U-PEREIRA', 'Pereira', 'Pereira', 'Centro Occidente', NULL),
    (45, 'U-CHINCHINA', 'Chinchiná', 'Chinchiná', 'Centro Occidente', NULL),
    (46, 'U-ARMENIA', 'Armenia', 'Armenia', 'Centro Occidente', NULL),
    (47, 'U-IBAGUE', 'Ibagué', 'Ibagué', 'Centro Sur', NULL),
    (48, 'U-LERIDA', 'Lérida', 'Lérida', 'Centro Sur', NULL),
    (49, 'U-LA-DORADA', 'La Dorada', 'La Dorada', 'Centro Sur', NULL),
    (50, 'U-NEIVA', 'Neiva', 'Neiva', 'Centro Sur', NULL),
    (51, 'U-GARZON', 'Garzón', 'Garzón', 'Centro Sur', NULL),
    (52, 'U-PITALITO', 'Pitalito', 'Pitalito', 'Centro Sur', NULL),
    (53, 'U-FLORENCIA', 'Florencia', 'Florencia', 'Centro Sur', NULL),
    (54, 'U-MOCOA', 'Mocoa', 'Mocoa', 'Centro Sur', NULL),
    (55, 'U-BUCARAMANGA', 'Bucaramanga', 'Bucaramanga', 'Oriente', NULL),
    (56, 'U-BARRANCABERMEJA', 'Barrancabermeja', 'Barrancabermeja', 'Oriente', NULL),
    (57, 'U-AGUACHICA', 'Aguachica', 'Aguachica', 'Oriente', NULL),
    (58, 'U-CUCUTA', 'Cúcuta', 'Cúcuta', 'Oriente', NULL),
    (59, 'U-OCANA', 'Ocaña', 'Ocaña', 'Oriente', NULL),
    (60, 'U-TIBU', 'Tibú', 'Tibú', 'Oriente', NULL),
    (61, 'U-EL-TARRA', 'El Tarra', 'El Tarra', 'Oriente', NULL),
    (62, 'U-SARDINATA', 'Sardinata', 'Sardinata', 'Oriente', NULL),
    (63, 'U-VILLAVICENCIO', 'Villavicencio', 'Villavicencio', 'Oriente', NULL),
    (64, 'U-YOPAL', 'Yopal', 'Yopal', 'Oriente', NULL),
    (65, 'U-OROCUE', 'Orocué', 'Orocué', 'Oriente', NULL),
    (66, 'U-INIRIDA', 'Inírida', 'Inírida', 'Oriente', NULL),
    (67, 'U-PUERTO-CARRENO', 'Puerto Carreño', 'Puerto Carreño', 'Oriente', NULL),
    (68, 'U-MITU', 'Mitú', 'Mitú', 'Oriente', NULL)
ON CONFLICT (id) DO UPDATE SET codigo = EXCLUDED.codigo, nombre = EXCLUDED.nombre, ciudad = EXCLUDED.ciudad,
    region = EXCLUDED.region, direccion = EXCLUDED.direccion, activa = true;

-- Cada centro arranca con las 11 zonas acordadas (Fase 1); se ajustan por centro después
INSERT INTO zona (sede_id, nombre)
SELECT s.id, z FROM sede s CROSS JOIN unnest(ARRAY[
    'Parqueadero', 'Aulas', 'Biblioteca', 'Auditorios', 'Baños', 'Terrazas',
    'Zonas verdes', 'CRAI - zona de descanso', 'Cafeterías', 'Admisiones', 'Sala de profesores'
]) AS z
WHERE s.id <= 68 AND NOT EXISTS (SELECT 1 FROM zona x WHERE x.sede_id = s.id AND x.nombre = z);

-- 2. Intentos de entrega que no pasaron la verificación (ADR-019). Al tercero, la coincidencia se
--    rechaza sola y el objeto vuelve a custodia. No se marca a la persona: puede ser el dueño real.
CREATE TABLE intento_entrega (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sede_id          smallint NOT NULL REFERENCES sede (id),
    coincidencia_id  uuid NOT NULL,
    motivo           text NOT NULL CHECK (motivo IN ('documento', 'pregunta_control', 'otro')),
    observaciones    text,
    registrado_por   uuid NOT NULL REFERENCES usuario (id),
    creado_en        timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (coincidencia_id, sede_id) REFERENCES coincidencia (id, sede_id)
);
CREATE INDEX intento_entrega_coincidencia_idx ON intento_entrega (coincidencia_id);
