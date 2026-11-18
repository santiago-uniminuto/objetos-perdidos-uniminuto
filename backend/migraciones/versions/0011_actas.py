"""Actas de entrega con consecutivo por sede y año, y foto del acta firmada.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-18
"""

from pathlib import Path

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    # Un comando por llamada (Citus no admite varios juntos; ver 0009)
    texto = (SQL / "0011_actas.sql").read_text(encoding="utf-8")
    sin_comentarios = "\n".join(linea for linea in texto.splitlines() if not linea.lstrip().startswith("--"))
    for sentencia in filter(str.strip, sin_comentarios.split(";")):
        op.execute(sentencia)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS entrega_numero_acta_idx")
    op.execute("ALTER TABLE entrega DROP COLUMN IF EXISTS acta_subida_por, DROP COLUMN IF EXISTS acta_subida_en, "
               "DROP COLUMN IF EXISTS acta_clave")
    op.execute("DROP TABLE IF EXISTS consecutivo_acta")
