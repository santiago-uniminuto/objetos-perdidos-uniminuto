"""Índices para el listado reciente del admin por sede (hallazgo de las pruebas de carga).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-14
"""

from pathlib import Path

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"


def upgrade() -> None:
    # Un comando por llamada: sobre Citus (perfil escala) un CREATE INDEX distribuido no admite varios juntos
    texto = (SQL / "0009_indices_listado_admin.sql").read_text(encoding="utf-8")
    sin_comentarios = "\n".join(linea for linea in texto.splitlines() if not linea.lstrip().startswith("--"))
    for sentencia in filter(str.strip, sin_comentarios.split(";")):
        op.execute(sentencia)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS reporte_sede_reciente_idx")
    op.execute("DROP INDEX IF EXISTS hallazgo_sede_reciente_idx")
