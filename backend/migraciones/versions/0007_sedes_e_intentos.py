"""Sedes reales de UNIMINUTO (centros universitarios por región) e intentos de entrega fallidos.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-14
"""

from pathlib import Path

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0007_sedes_e_intentos.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Las sedes y zonas nuevas se quedan (puede haber reportes en ellas); solo se quitan las columnas nuevas
    op.execute("DROP TABLE IF EXISTS intento_entrega; ALTER TABLE sede DROP COLUMN IF EXISTS direccion; "
               "ALTER TABLE sede DROP COLUMN IF EXISTS region;")
