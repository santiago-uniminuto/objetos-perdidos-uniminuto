"""Diagnóstico del almacenamiento de fotos: prueba cada paso y dice cuál falla y por qué.

    docker compose exec api python -m app.diagnostico_fotos
"""

import io
import os
import socket
import sys
from urllib.parse import urlparse

from PIL import Image


def paso(nombre: str, fn):
    try:
        r = fn()
        print(f"  OK     {nombre}" + (f": {r}" if r not in (None, True) else ""))
        return True
    except Exception as exc:  # noqa: BLE001 - es un diagnóstico: mostrar todo
        print(f"  FALLA  {nombre}: {type(exc).__name__}: {exc}")
        return False


def main() -> int:
    from app import fotos

    endpoint = os.environ.get("S3_ENDPOINT")
    local = os.environ.get("FOTOS_LOCAL", "./fotos-local")
    print(f"Almacén: {'S3 en ' + endpoint if endpoint else 'carpeta local ' + local}")
    print(f"Bucket:  {os.environ.get('FOTOS_BUCKET', 'fotos')}   "
          f"Llave de acceso: {os.environ.get('S3_ACCESS_KEY', '(sin definir)')}")
    if endpoint:
        u = urlparse(endpoint)
        if not paso(f"resolver el nombre '{u.hostname}'", lambda: socket.gethostbyname(u.hostname)):
            print("  -> El contenedor 'lake' no está en la red: ¿está arriba el perfil datos? "
                  "(docker compose ps lake)")
            return 1
        if not paso(f"conectar a {u.hostname}:{u.port or 80}",
                    lambda: socket.create_connection((u.hostname, u.port or 80), timeout=3).close()):
            print("  -> SeaweedFS no acepta conexiones: docker compose logs lake --tail 30")
            return 1
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), (20, 80, 160)).save(buf, "JPEG")
    foto = fotos.procesar(buf.getvalue())
    a = fotos.almacen()
    clave = "diagnostico/prueba.webp"
    ok = all([
        paso("crear o encontrar el bucket", getattr(a, "_asegurar_bucket", lambda: None)),
        paso("guardar un archivo de prueba", lambda: a.guardar(clave, foto.archivos["mini"])),
        paso("leerlo", lambda: f"{len(a.leer(clave))} bytes"),
        paso("borrarlo", lambda: a.borrar(clave)),
    ])
    print("Todo bien: las fotos se pueden guardar." if ok else
          "Copia este resultado: el primer FALLA dice qué arreglar (credenciales, bucket o red).\n"
          "  Si guardar da InternalError: SeaweedFS se quedó sin volúmenes; el lake debe arrancar con "
          "-volume.max=0 (docker-compose.yml) y recrearse: docker compose up -d lake")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
