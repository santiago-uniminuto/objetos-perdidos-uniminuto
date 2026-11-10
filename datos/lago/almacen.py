"""Acceso al lake con pyarrow: S3 (SeaweedFS) en producción, carpeta local en pruebas.

pyarrow trae su propio cliente S3, así que no hace falta boto3 ni la extensión httpfs de
DuckDB (que se descarga de internet en tiempo de ejecución).
"""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.fs as pafs
import pyarrow.parquet as pq


class Lago:
    def __init__(self, fs: pafs.FileSystem, raiz: str):
        self.fs, self.raiz = fs, raiz.rstrip("/")

    @classmethod
    def desde_entorno(cls) -> "Lago":
        endpoint = os.environ.get("S3_ENDPOINT")
        if endpoint:
            esquema, _, host = endpoint.partition("://")
            fs = pafs.S3FileSystem(
                endpoint_override=host or esquema, scheme=esquema if host else "http",
                access_key=os.environ["S3_ACCESS_KEY"], secret_key=os.environ["S3_SECRET_KEY"],
                allow_bucket_creation=True,
            )
            bucket = os.environ.get("S3_BUCKET", "lake")
            fs.create_dir(bucket)
            return cls(fs, bucket)
        raiz = os.path.abspath(os.environ.get("LAGO_LOCAL", "./lago-local"))
        os.makedirs(raiz, exist_ok=True)
        return cls(pafs.LocalFileSystem(), raiz)

    def ruta(self, relativa: str) -> str:
        return f"{self.raiz}/{relativa.strip('/')}"

    def agregar(self, carpeta: str, tabla: pa.Table) -> str:
        """Bronze: agrega un archivo nuevo (nunca reescribe lo anterior)."""
        destino = self.ruta(f"{carpeta}/parte-{uuid.uuid4().hex[:12]}.parquet")
        self.fs.create_dir(destino.rsplit("/", 1)[0])
        pq.write_table(tabla, destino, filesystem=self.fs, compression="zstd")
        return destino

    def reemplazar(self, carpeta: str, tabla: pa.Table, particiones: list[str] | None = None) -> None:
        """Silver/gold: se reconstruyen completas desde bronze (idempotente)."""
        base = self.ruta(carpeta)
        if self.existe(carpeta):
            self.fs.delete_dir(base)
        self.fs.create_dir(base)
        if particiones:
            ds.write_dataset(tabla, base, filesystem=self.fs, format="parquet", partitioning=particiones,
                             partitioning_flavor="hive", existing_data_behavior="overwrite_or_ignore")
        else:
            pq.write_table(tabla, f"{base}/datos.parquet", filesystem=self.fs, compression="zstd")

    def existe(self, carpeta: str) -> bool:
        return self.fs.get_file_info(self.ruta(carpeta)).type != pafs.FileType.NotFound

    def dataset(self, carpeta: str) -> ds.Dataset | None:
        """Vista perezosa: DuckDB la recorre por partes sin cargarla entera en memoria."""
        if not self.existe(carpeta):
            return None
        return ds.dataset(self.ruta(carpeta), filesystem=self.fs, format="parquet", partitioning="hive")

    def compactar(self, carpeta: str, max_partes: int = 4) -> int:
        """Une los Parquet pequeños de cada partición (bronze recibe un archivo por lote y día).

        Escribe primero el archivo unido y luego borra los viejos: si se cae en medio quedan
        duplicados, que silver descarta por outbox_id. Devuelve cuántas particiones compactó.
        """
        if not self.existe(carpeta):
            return 0
        particiones = [p.path for p in self.fs.get_file_info(pafs.FileSelector(self.ruta(carpeta)))
                       if p.type == pafs.FileType.Directory]
        # En S3 cada partición es lenta por la red (leer + escribir + borrar): se hacen en paralelo
        with ThreadPoolExecutor(max_workers=int(os.environ.get("LAGO_HILOS", "8"))) as ex:
            return sum(ex.map(lambda p: self._compactar_particion(p, max_partes), particiones))

    def _compactar_particion(self, ruta: str, max_partes: int) -> int:
        archivos = [f.path for f in self.fs.get_file_info(pafs.FileSelector(ruta)) if f.path.endswith(".parquet")]
        if len(archivos) <= max_partes:
            return 0
        tabla = ds.dataset(archivos, filesystem=self.fs, format="parquet").to_table()
        pq.write_table(tabla, f"{ruta}/compacto-{uuid.uuid4().hex[:12]}.parquet", filesystem=self.fs,
                       compression="zstd")
        for a in archivos:
            self.fs.delete_file(a)
        return 1

    def leer(self, carpeta: str) -> pa.Table | None:
        """Lee todos los Parquet de una carpeta (con particiones hive). None si no hay datos."""
        if not self.existe(carpeta):
            return None
        dataset = ds.dataset(self.ruta(carpeta), filesystem=self.fs, format="parquet", partitioning="hive")
        tabla = dataset.to_table()
        return tabla if tabla.num_rows else None
