"""Vista pública con código de categoría y zona para filtros.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-10
"""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    op.execute((SQL / "0002_vista_publica_filtros.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Volver a la vista de 0001 exige recrearla (no se pueden quitar columnas con OR REPLACE)
    op.execute("DROP VIEW vista_publica_objetos;")
    sql_0001 = (SQL / "0001_esquema_inicial.sql").read_text(encoding="utf-8")
    inicio = sql_0001.index("CREATE VIEW vista_publica_objetos")
    fin = sql_0001.index("-- ----------------------------------------------------- datos semilla")
    op.execute(sql_0001[inicio:fin])
