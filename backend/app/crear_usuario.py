"""Crea un usuario administrador o auditor desde la consola.

    docker compose run --rm api python -m app.crear_usuario --email admin@uniminuto.edu.co \\
        --nombre "Admin Sede" --rol admin_sede --sede 1

La contraseña se pide por teclado (no queda en el historial de la consola).
"""

import argparse
import getpass
import sys

import psycopg

from app.config import get_settings
from app.seguridad import hashear


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--nombre", required=True)
    p.add_argument("--rol", choices=["admin_sede", "auditor"], default="admin_sede")
    p.add_argument("--sede", type=int, default=None)
    a = p.parse_args()

    contrasena = getpass.getpass("Contraseña (mínimo 10 caracteres): ")
    if len(contrasena) < 10 or contrasena != getpass.getpass("Repítela: "):
        print("Las contraseñas no coinciden o son muy cortas.", file=sys.stderr)
        return 1
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute(
            "INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) VALUES (%s, %s, %s, %s, %s)",
            (a.sede, a.email, a.nombre, hashear(contrasena), a.rol),
        )
    print(f"Usuario {a.email} ({a.rol}) creado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
