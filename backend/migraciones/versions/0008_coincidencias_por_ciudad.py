"""Coincidencias entre sedes de la misma ciudad (sede de custodia) y estado 'entregado' al entregar.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-14
"""

from pathlib import Path

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0008_coincidencias_por_ciudad.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Las coincidencias entre sedes no caben en el esquema anterior: se borran (con sus intentos y entregas)
    op.execute("""
        ALTER TABLE intento_entrega DROP CONSTRAINT intento_entrega_pkey;
        ALTER TABLE intento_entrega ADD PRIMARY KEY (id);
        DELETE FROM intento_entrega i USING coincidencia c
            WHERE i.coincidencia_id = c.id AND c.sede_id <> c.reporte_sede_id;
        DELETE FROM entrega e USING coincidencia c WHERE e.coincidencia_id = c.id AND c.sede_id <> c.reporte_sede_id;
        DELETE FROM coincidencia WHERE sede_id <> reporte_sede_id;
        UPDATE reporte_perdida SET estado = 'cerrado' WHERE estado = 'entregado';
        UPDATE hallazgo SET estado = 'cerrado' WHERE estado = 'entregado';
        DROP INDEX IF EXISTS coincidencia_reporte_sede_idx;
        ALTER TABLE coincidencia DROP CONSTRAINT coincidencia_reporte_fk;
        ALTER TABLE coincidencia DROP CONSTRAINT coincidencia_reporte_sede_fk;
        ALTER TABLE coincidencia DROP COLUMN reporte_sede_id;
        ALTER TABLE coincidencia ADD FOREIGN KEY (reporte_id, reporte_creado_en, sede_id)
            REFERENCES reporte_perdida (id, creado_en, sede_id);
    """)
