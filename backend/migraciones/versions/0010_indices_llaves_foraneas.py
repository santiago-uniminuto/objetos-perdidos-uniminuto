"""Índices en las columnas de llaves foráneas (coincidencia, entrega y consentimiento): borrados y matcher rápidos.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-15
"""

from pathlib import Path

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parent.parent / "sql"
INDICES = ("coincidencia_reporte_idx", "coincidencia_hallazgo_idx", "entrega_estudiante_idx",
           "consentimiento_estudiante_todos_idx")


def upgrade() -> None:
    # Un comando por llamada (Citus no admite varios juntos; ver 0009)
    texto = (SQL / "0010_indices_llaves_foraneas.sql").read_text(encoding="utf-8")
    sin_comentarios = "\n".join(linea for linea in texto.splitlines() if not linea.lstrip().startswith("--"))
    for sentencia in filter(str.strip, sin_comentarios.split(";")):
        op.execute(sentencia)


def downgrade() -> None:
    for indice in INDICES:
        op.execute(f"DROP INDEX IF EXISTS {indice}")
