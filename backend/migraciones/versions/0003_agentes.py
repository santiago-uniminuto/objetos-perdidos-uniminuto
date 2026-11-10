"""Soporte para los agentes: offsets por consumidor del outbox y ficha normalizada.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-10
"""

from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0003_agentes.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS objeto_embedding_candidatos_idx;
        ALTER TABLE objeto_embedding DROP COLUMN IF EXISTS ficha;
        DROP TABLE IF EXISTS consumidor_outbox;
        """
    )
