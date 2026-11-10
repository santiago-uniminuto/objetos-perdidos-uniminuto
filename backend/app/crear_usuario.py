"""Cuentas del personal desde la consola (no hay registro abierto en la web).

Crear un admin de sede o un auditor (la contraseña se pide por teclado, no queda en el historial):

    docker compose exec api python -m app.crear_usuario --email admin@uniminuto.edu.co \\
        --nombre "Admin Sede" --rol admin_sede --sede 1

Restablecer la contraseña de alguien que no recibe el correo (o si el SMTP no está configurado):
imprime un enlace de un solo uso que vence en 30 minutos; el dueño de la cuenta pone ahí su clave nueva.

    docker compose exec api python -m app.crear_usuario --restablecer --email admin@uniminuto.edu.co

Desactivar o reactivar una cuenta (p. ej., alguien deja el cargo):

    docker compose exec api python -m app.crear_usuario --desactivar --email admin@uniminuto.edu.co
"""

import argparse
import getpass
import sys

import psycopg
from psycopg.rows import dict_row

from app import contrasenas
from app.config import get_settings
from app.errores import ErrorApp
from app.registro import auditar
from app.seguridad import hashear


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--email", required=True)
    p.add_argument("--nombre")
    p.add_argument("--rol", choices=["admin_sede", "auditor"], default="admin_sede")
    p.add_argument("--sede", type=int, default=None)
    accion = p.add_mutually_exclusive_group()
    accion.add_argument("--restablecer", action="store_true", help="imprime un enlace para poner clave nueva")
    accion.add_argument("--desactivar", action="store_true")
    accion.add_argument("--reactivar", action="store_true")
    a = p.parse_args()

    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        if a.restablecer or a.desactivar or a.reactivar:
            u = conn.execute("SELECT id, sede_id, activo FROM usuario WHERE lower(email) = lower(%s)",
                             (a.email,)).fetchone()
            if u is None:
                print(f"No existe una cuenta con el correo {a.email}.", file=sys.stderr)
                return 1
            if a.restablecer:
                enlace = contrasenas.crear_enlace(conn, u["id"], "consola")
                auditar(conn, None, "solicitud_restablecimiento", "usuario", u["id"], u["sede_id"],
                        detalle={"via": "consola"})
                print(f"Enlace de un solo uso (vence en {get_settings().restablecer_minutos} min). "
                      f"Entrégalo SOLO al dueño de la cuenta:\n\n{enlace}\n")
            else:
                conn.execute("UPDATE usuario SET activo = %s WHERE id = %s", (a.reactivar, u["id"]))
                auditar(conn, None, "actualizar", "usuario", u["id"], u["sede_id"],
                        detalle={"activo": a.reactivar, "via": "consola"})
                print(f"Cuenta {a.email} {'reactivada' if a.reactivar else 'desactivada'}.")
            return 0

        if not a.nombre:
            p.error("--nombre es obligatorio para crear una cuenta")
        contrasena = getpass.getpass(f"Contraseña (mínimo {get_settings().contrasena_min} caracteres): ")
        try:
            contrasenas.validar_nueva(contrasena, a.email)
        except ErrorApp as exc:
            print(exc.mensaje, file=sys.stderr)
            return 1
        if contrasena != getpass.getpass("Repítela: "):
            print("Las contraseñas no coinciden.", file=sys.stderr)
            return 1
        conn.execute(
            "INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) VALUES (%s, %s, %s, %s, %s)",
            (a.sede, a.email, a.nombre, hashear(contrasena), a.rol),
        )
    print(f"Usuario {a.email} ({a.rol}) creado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
