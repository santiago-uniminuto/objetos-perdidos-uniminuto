"""Entorno de Alembic. Las migraciones son SQL explícito (curso de bases de datos):
cada versión ejecuta un archivo de migraciones/sql/."""

import os

from alembic import context
from sqlalchemy import create_engine, pool


def _url() -> str:
    url = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:5432/objetos_perdidos")
    # SQLAlchemy necesita el nombre del driver (psycopg 3)
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
