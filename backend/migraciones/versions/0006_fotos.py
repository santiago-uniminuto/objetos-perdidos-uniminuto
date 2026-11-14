"""Fotos de los objetos.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-14
"""

from pathlib import Path

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0006_fotos.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS vista_publica_fotos; DROP TABLE IF EXISTS foto_objeto;")
