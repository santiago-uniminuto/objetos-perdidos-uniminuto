"""Portal público solo con objetos perdidos; restablecimiento de contraseña.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-10
"""

from pathlib import Path

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0005_publico_y_contrasenas.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Los valores nuevos del enum se quedan (PostgreSQL no permite quitarlos); no estorban.
    op.execute("DROP TABLE IF EXISTS restablecimiento_contrasena; DROP VIEW vista_publica_objetos;")
    op.execute((SQL / "0002_vista_publica_filtros.sql").read_text(encoding="utf-8").replace(
        "CREATE OR REPLACE VIEW", "CREATE VIEW"))
