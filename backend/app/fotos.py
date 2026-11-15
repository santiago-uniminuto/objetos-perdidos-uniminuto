"""Fotos de los objetos (ADR-018): procesamiento seguro y almacenamiento en SeaweedFS.

Cada foto subida se abre con Pillow (con límite de píxeles contra "bombas de descompresión"),
se endereza según EXIF, se re-codifica a WebP en dos tamaños (1600 y 480 px) y así pierde
TODOS los metadatos (GPS, modelo del celular, fecha). El original nunca se guarda.

Almacén: S3 (SeaweedFS, bucket FOTOS_BUCKET) si hay S3_ENDPOINT; si no, una carpeta (pruebas).
"""

import hashlib
import io
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.errores import ErrorApp

log = logging.getLogger("fotos")
MAX_BYTES = 8 * 1024 * 1024
MAX_FOTOS = 3
TAMANOS = {"grande": 1600, "mini": 480}
FORMATOS = {"JPEG", "PNG", "WEBP", "HEIF", "MPO"}
Image.MAX_IMAGE_PIXELS = 40_000_000  # ~ 40 MP: más que eso se rechaza (DecompressionBombError)

try:  # fotos de iPhone (HEIC); si la librería no está, se rechazan con un mensaje claro
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class FotoProcesada:
    archivos: dict[str, bytes]  # tamaño -> WebP
    ancho: int
    alto: int
    sha256: bytes


def procesar(datos: bytes) -> FotoProcesada:
    if len(datos) > MAX_BYTES:
        raise ErrorApp(413, "foto_muy_grande", "La foto pesa más de 8 MB. Toma otra o redúcela.")
    try:
        with Image.open(io.BytesIO(datos)) as img:
            if img.format not in FORMATOS:
                raise ErrorApp(415, "formato_no_admitido", "Usa una foto JPG, PNG, WebP o HEIC.")
            img = ImageOps.exif_transpose(img)
            img = img.convert("RGB")  # descarta transparencia, perfiles raros y metadatos
            archivos = {}
            for nombre, lado in TAMANOS.items():
                copia = img.copy()
                copia.thumbnail((lado, lado), Image.Resampling.LANCZOS)
                salida = io.BytesIO()
                copia.save(salida, "WEBP", quality=82, method=4)  # sin exif=: el WebP sale limpio
                archivos[nombre] = salida.getvalue()
            ancho, alto = img.size
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ErrorApp(415, "formato_no_admitido", "El archivo no es una foto válida o es demasiado grande.") from exc
    final = Image.open(io.BytesIO(archivos["grande"]))
    return FotoProcesada(archivos, final.width, final.height, hashlib.sha256(datos).digest())


# ------------------------------------------------------------------ almacén
class AlmacenLocal:
    def __init__(self, raiz: str):
        self.raiz = Path(raiz)

    def guardar(self, clave: str, datos: bytes) -> None:
        ruta = self.raiz / clave
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(datos)

    def leer(self, clave: str) -> bytes:
        try:
            return (self.raiz / clave).read_bytes()
        except FileNotFoundError as exc:
            raise ErrorApp(404, "no_encontrado", "La foto no existe") from exc

    def borrar(self, clave: str) -> None:
        (self.raiz / clave).unlink(missing_ok=True)


class AlmacenS3:
    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = os.environ.get("FOTOS_BUCKET", "fotos")
        self.s3 = boto3.client(
            "s3", endpoint_url=os.environ["S3_ENDPOINT"], aws_access_key_id=os.environ["S3_ACCESS_KEY"],
            aws_secret_access_key=os.environ["S3_SECRET_KEY"], region_name="us-east-1",
            # boto3 >= 1.36 agrega checksums CRC32 "por defecto"; algunos S3 compatibles no los aceptan
            config=Config(s3={"addressing_style": "path"}, connect_timeout=3, read_timeout=10,
                          retries={"max_attempts": 2}, request_checksum_calculation="when_required",
                          response_checksum_validation="when_required"),
        )
        self._bucket_listo = False

    def _asegurar_bucket(self) -> None:
        if not self._bucket_listo:
            from botocore.exceptions import ClientError

            try:
                self.s3.head_bucket(Bucket=self.bucket)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") not in ("404", "NoSuchBucket", "NotFound"):
                    raise  # p. ej. 403 por credenciales: no es que falte el bucket
                self.s3.create_bucket(Bucket=self.bucket)
            self._bucket_listo = True

    def guardar(self, clave: str, datos: bytes) -> None:
        self._asegurar_bucket()
        self.s3.put_object(Bucket=self.bucket, Key=clave, Body=datos, ContentType="image/webp")

    def leer(self, clave: str) -> bytes:
        try:
            return self.s3.get_object(Bucket=self.bucket, Key=clave)["Body"].read()
        except self.s3.exceptions.NoSuchKey as exc:
            raise ErrorApp(404, "no_encontrado", "La foto no existe") from exc

    def borrar(self, clave: str) -> None:
        self.s3.delete_object(Bucket=self.bucket, Key=clave)


@lru_cache
def almacen() -> AlmacenLocal | AlmacenS3:
    if os.environ.get("S3_ENDPOINT"):
        return AlmacenS3()
    return AlmacenLocal(os.environ.get("FOTOS_LOCAL", "./fotos-local"))


def guardar(clave: str, foto: FotoProcesada) -> None:
    try:
        for nombre, datos in foto.archivos.items():
            almacen().guardar(f"{clave}/{nombre}.webp", datos)
    except ErrorApp:
        raise
    except Exception as exc:  # noqa: BLE001 - p. ej. SeaweedFS apagado (perfil datos)
        # El detalle va al log (docker compose logs api); al usuario, un mensaje claro
        log.error('"no se pudo guardar la foto en %s: %s: %s"', os.environ.get("S3_ENDPOINT", "carpeta local"),
                  type(exc).__name__, str(exc)[:300].replace('"', "'"))
        raise ErrorApp(503, "almacen_no_disponible",
                       "No se pudo guardar la foto: el almacenamiento no responde. Intenta de nuevo.") from exc


def leer(clave: str, tamano: str) -> bytes:
    if tamano not in TAMANOS:
        raise ErrorApp(422, "validacion", "Tamaño de foto no válido")
    try:
        return almacen().leer(f"{clave}/{tamano}.webp")
    except ErrorApp:
        raise
    except Exception as exc:  # noqa: BLE001
        log.error('"no se pudo leer la foto: %s: %s"', type(exc).__name__, str(exc)[:300].replace('"', "'"))
        raise ErrorApp(503, "almacen_no_disponible", "El almacenamiento de fotos no responde.") from exc


def borrar(clave: str) -> None:
    for nombre in TAMANOS:
        almacen().borrar(f"{clave}/{nombre}.webp")
