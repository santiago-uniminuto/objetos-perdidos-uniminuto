"""Esquema inicial: catálogos, personas, operación particionada, auditoría, outbox.

Revision ID: 0001
Revises:
Create Date: 2026-11-09
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0001_esquema_inicial.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(
        """
        DROP VIEW IF EXISTS vista_publica_objetos;
        DROP TABLE IF EXISTS entrega, coincidencia, objeto_embedding, outbox CASCADE;
        DROP TABLE IF EXISTS auditoria, hallazgo, reporte_perdida CASCADE;
        DROP TABLE IF EXISTS consentimiento, estudiante, usuario, zona, categoria, sede CASCADE;
        DROP FUNCTION IF EXISTS crear_particiones_mensuales(text, date, date);
        DROP FUNCTION IF EXISTS auditoria_inmutable();
        DROP TYPE IF EXISTS accion_auditoria, tipo_objeto, estado_coincidencia,
                            estado_hallazgo, estado_reporte, rol_usuario;
        """
    )
