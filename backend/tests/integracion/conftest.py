"""Configuración común de las pruebas de integración."""

import os
import tempfile

# Las fotos van a una carpeta temporal en vez de SeaweedFS (antes de que la app cree el almacén)
os.environ.pop("S3_ENDPOINT", None)
os.environ.setdefault("FOTOS_LOCAL", tempfile.mkdtemp(prefix="fotos-prueba-"))

from tests.integracion.test_api import entorno  # noqa: E402,F401  (fixture compartida con test_fotos)
