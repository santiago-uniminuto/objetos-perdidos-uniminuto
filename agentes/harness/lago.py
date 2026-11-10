"""Lectura de la capa gold del lake (solo lectura; quien escribe es el servicio `etl`).

Mismas variables que el ETL: S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY/S3_BUCKET para SeaweedFS,
o LAGO_LOCAL para una carpeta (pruebas). Sin ninguna de las dos, no hay lake: el analista no corre.
"""

import os

import pyarrow.dataset as ds
import pyarrow.fs as pafs


class LectorGold:
    def __init__(self, fs: pafs.FileSystem, raiz: str):
        self.fs, self.raiz = fs, raiz.rstrip("/")

    @classmethod
    def desde_entorno(cls) -> "LectorGold | None":
        endpoint = os.environ.get("S3_ENDPOINT")
        if endpoint:
            esquema, _, host = endpoint.partition("://")
            fs = pafs.S3FileSystem(endpoint_override=host or esquema, scheme=esquema if host else "http",
                                   access_key=os.environ["S3_ACCESS_KEY"], secret_key=os.environ["S3_SECRET_KEY"])
            return cls(fs, os.environ.get("S3_BUCKET", "lake"))
        if os.environ.get("LAGO_LOCAL"):
            return cls(pafs.LocalFileSystem(), os.path.abspath(os.environ["LAGO_LOCAL"]))
        return None

    def tabla(self, nombre: str) -> list[dict]:
        """Filas de gold/<nombre> como diccionarios (las tablas gold son pequeñas). [] si no existe."""
        ruta = f"{self.raiz}/gold/{nombre}"
        if self.fs.get_file_info(ruta).type == pafs.FileType.NotFound:
            return []
        return ds.dataset(ruta, filesystem=self.fs, format="parquet").to_table().to_pylist()
