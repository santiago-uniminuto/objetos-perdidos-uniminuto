"""Respaldos de Objetos Perdidos (Fase 7): PostgreSQL + fotos, con retención y verificación.

Qué se respalda y qué no (ADR-022):
* PostgreSQL: la fuente de verdad (ADR-003). pg_dump en formato custom (comprimido) cada día.
* Fotos (bucket `fotos` de SeaweedFS): espejo exacto en disco. Las fotos no se pueden reconstruir.
* NO se respalda el lake (bronze/silver/gold): se reconstruye desde el outbox, que va en el dump.
* NO se respalda MongoDB: trazas de agentes y copia de eventos; no es fuente de verdad.

Comandos:
    python3 respaldo.py servicio                 # bucle: un respaldo diario a RESPALDO_HORA (lo usa compose)
    python3 respaldo.py respaldar                # respaldo inmediato
    python3 respaldo.py verificar [ARCHIVO]      # restaura en una base temporal y compara conteos (no toca nada)
    python3 respaldo.py restaurar ARCHIVO --confirmar [--fotos]   # reemplaza la base real (¡detén la API antes!)

Variables: PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE (las de libpq) · S3_ENDPOINT, S3_ACCESS_KEY,
S3_SECRET_KEY, FOTOS_BUCKET · RESPALDO_DIR (/respaldos) · RESPALDO_HORA (02:30) · RESPALDO_DIAS (7) ·
RESPALDO_AL_INICIAR (true).
"""

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DIR = Path(os.environ.get("RESPALDO_DIR", "/respaldos"))
DIR_BD, DIR_FOTOS = DIR / "postgres", DIR / "fotos"
BD = os.environ.get("PGDATABASE", "objetos_perdidos")
BD_PRUEBA = "verificacion_respaldo"
# Tablas cuyos conteos se comparan al verificar (las que importan para la operación)
TABLAS = ("sede", "usuario", "estudiante", "consentimiento", "reporte_perdida", "hallazgo", "coincidencia",
          "entrega", "foto_objeto", "auditoria", "outbox")


def log(msg: str) -> None:
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def ejecutar(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, text=True, capture_output=True, **kw)  # noqa: S603 - pg_dump/psql, sin shell


def psql(sql: str, base: str = BD) -> str:
    return ejecutar(["psql", "-X", "-At", "-v", "ON_ERROR_STOP=1", "-d", base, "-c", sql]).stdout.strip()


# ------------------------------------------------------------------------------------------- PostgreSQL
def respaldar_bd() -> Path:
    DIR_BD.mkdir(parents=True, exist_ok=True)
    destino = DIR_BD / f"{BD}_{dt.datetime.now():%Y%m%d_%H%M%S}.dump"
    parcial = destino.with_suffix(".parcial")
    t0 = time.monotonic()
    # Formato custom: comprimido y restaurable por partes. Se escribe a un .parcial y se renombra al final:
    # un respaldo cortado a la mitad nunca queda con nombre de respaldo válido.
    ejecutar(["pg_dump", "-Fc", "-Z", "6", "--no-owner", "--no-privileges", "-d", BD, "-f", str(parcial)])
    parcial.rename(destino)
    log(f"PostgreSQL: {destino.name} ({destino.stat().st_size / 1e6:.1f} MB, {time.monotonic() - t0:.0f} s)")
    return destino


def podar(dias: int) -> None:
    """Borra dumps de más de `dias` días, pero nunca el más reciente."""
    dumps = sorted(DIR_BD.glob(f"{BD}_*.dump"))
    limite = time.time() - dias * 86400
    for viejo in dumps[:-1]:
        if viejo.stat().st_mtime < limite:
            viejo.unlink()
            log(f"retención: borrado {viejo.name}")
    for parcial in DIR_BD.glob("*.parcial"):  # restos de un respaldo interrumpido
        parcial.unlink()


# ------------------------------------------------------------------------------------------------ fotos
def cliente_s3():
    import boto3
    from botocore.config import Config

    try:  # botocore >= 1.36 manda checksums que SeaweedFS no acepta; las versiones viejas (Debian) no los mandan
        config = Config(request_checksum_calculation="when_required", response_checksum_validation="when_required")
    except TypeError:
        config = Config()
    return boto3.client("s3", endpoint_url=os.environ["S3_ENDPOINT"],
                        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
                        aws_secret_access_key=os.environ["S3_SECRET_KEY"], region_name="us-east-1", config=config)


def respaldar_fotos() -> dict:
    """Espejo exacto del bucket: descarga lo nuevo y borra lo que ya no existe (retención de 90 días, ADR-018).

    Las claves de las fotos no se reutilizan, así que lo que ya está en disco no hay que volver a bajarlo.
    """
    if not os.environ.get("S3_ENDPOINT"):
        log("fotos: sin S3_ENDPOINT, se omiten")
        return {}
    bucket = os.environ.get("FOTOS_BUCKET", "fotos")
    s3 = cliente_s3()
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception as exc:  # noqa: BLE001 - el lake puede no estar encendido: no detiene el respaldo de la BD
        log(f"fotos: el bucket '{bucket}' no está disponible ({type(exc).__name__}); se omiten")
        return {}
    DIR_FOTOS.mkdir(parents=True, exist_ok=True)
    en_bucket, nuevas = set(), 0
    for pagina in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in pagina.get("Contents", []):
            clave = obj["Key"]
            en_bucket.add(clave)
            local = DIR_FOTOS / clave
            if local.exists() and local.stat().st_size == obj["Size"]:
                continue
            local.parent.mkdir(parents=True, exist_ok=True)
            s3.download_file(bucket, clave, str(local))
            nuevas += 1
    borradas = 0
    for local in [p for p in DIR_FOTOS.rglob("*") if p.is_file()]:
        if local.relative_to(DIR_FOTOS).as_posix() not in en_bucket:
            local.unlink()
            borradas += 1
    log(f"fotos: {len(en_bucket)} en el bucket · {nuevas} nuevas · {borradas} borradas del espejo")
    return {"total": len(en_bucket), "nuevas": nuevas, "borradas": borradas}


def restaurar_fotos() -> None:
    bucket = os.environ.get("FOTOS_BUCKET", "fotos")
    s3 = cliente_s3()
    try:
        s3.head_bucket(Bucket=bucket)
    except Exception:  # noqa: BLE001
        s3.create_bucket(Bucket=bucket)
    archivos = [p for p in DIR_FOTOS.rglob("*") if p.is_file()]
    for local in archivos:
        s3.upload_file(str(local), bucket, local.relative_to(DIR_FOTOS).as_posix())
    log(f"fotos: {len(archivos)} subidas al bucket '{bucket}'")


# --------------------------------------------------------------------------------------------- comandos
def respaldar(dias: int) -> None:
    dump = respaldar_bd()
    fotos = respaldar_fotos()
    podar(dias)
    resumen = {"fecha": dt.datetime.now().isoformat(timespec="seconds"), "postgres": dump.name,
               "postgres_mb": round(dump.stat().st_size / 1e6, 1), "fotos": fotos, "retencion_dias": dias}
    (DIR / "ULTIMO.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")


def conteos(base: str) -> dict[str, int]:
    return {t: int(psql(f"SELECT count(*) FROM {t}", base)) for t in TABLAS}  # noqa: S608 - nombres fijos


def verificar(archivo: Path | None) -> int:
    """Restaura el dump en una base temporal, compara conteos con la base viva y la borra. No toca la real."""
    archivo = archivo or max(DIR_BD.glob(f"{BD}_*.dump"), key=lambda p: p.stat().st_mtime, default=None)
    if archivo is None:
        log("no hay respaldos para verificar")
        return 1
    log(f"verificando {archivo.name} en la base temporal '{BD_PRUEBA}'")
    psql(f"DROP DATABASE IF EXISTS {BD_PRUEBA} WITH (FORCE)", "postgres")
    psql(f"CREATE DATABASE {BD_PRUEBA}", "postgres")
    try:
        t0 = time.monotonic()
        ejecutar(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", "-d", BD_PRUEBA, str(archivo)])
        log(f"restaurado sin errores en {time.monotonic() - t0:.0f} s")
        restaurada, viva = conteos(BD_PRUEBA), conteos(BD)
        print(f"\n{'tabla':<18}{'en el respaldo':>16}{'base actual':>14}")
        for t in TABLAS:
            print(f"{t:<18}{restaurada[t]:>16,}{viva[t]:>14,}".replace(",", "."))
        vacias = [t for t in ("sede", "usuario") if restaurada[t] == 0]
        if vacias:
            log(f"ERROR: el respaldo no tiene filas en {vacias}")
            return 1
        print("\nLas diferencias son lo que cambió después del respaldo (p. ej. auditoría y outbox siguen creciendo).")
        log("verificación OK")
        return 0
    finally:
        psql(f"DROP DATABASE IF EXISTS {BD_PRUEBA} WITH (FORCE)", "postgres")


def restaurar(archivo: Path, confirmar: bool, fotos: bool) -> int:
    if not confirmar:
        print("Esto REEMPLAZA la base real con el respaldo. Detén antes api, agentes y etl:\n"
              "    docker compose stop api agentes etl\n"
              "y repite el comando con --confirmar.")
        return 1
    log(f"restaurando {archivo.name} sobre '{BD}'")
    psql(f"DROP DATABASE IF EXISTS {BD} WITH (FORCE)", "postgres")
    psql(f"CREATE DATABASE {BD}", "postgres")
    ejecutar(["pg_restore", "--no-owner", "--no-privileges", "--exit-on-error", "-d", BD, str(archivo)])
    log("base restaurada")
    if fotos:
        restaurar_fotos()
    return 0


def servicio(hora: str, dias: int, al_iniciar: bool) -> None:
    hh, mm = (int(x) for x in hora.split(":"))
    log(f"servicio de respaldo: todos los días a las {hora}, retención de {dias} días, carpeta {DIR}")
    if al_iniciar:
        intentar(dias)
    while True:
        ahora = dt.datetime.now()
        proximo = ahora.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if proximo <= ahora:
            proximo += dt.timedelta(days=1)
        log(f"próximo respaldo: {proximo:%Y-%m-%d %H:%M}")
        time.sleep((proximo - ahora).total_seconds())
        intentar(dias)


def intentar(dias: int) -> None:
    """Un fallo (base apagada, disco lleno) se registra y se reintenta mañana; el servicio no se cae."""
    try:
        respaldar(dias)
    except subprocess.CalledProcessError as exc:
        log(f"ERROR en el respaldo: {exc.cmd[0]} terminó con {exc.returncode}: {exc.stderr.strip()[:500]}")
    except Exception as exc:  # noqa: BLE001
        log(f"ERROR en el respaldo: {type(exc).__name__}: {exc}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="comando", required=True)
    sub.add_parser("servicio")
    sub.add_parser("respaldar")
    v = sub.add_parser("verificar")
    v.add_argument("archivo", nargs="?", type=Path)
    r = sub.add_parser("restaurar")
    r.add_argument("archivo", type=Path)
    r.add_argument("--confirmar", action="store_true")
    r.add_argument("--fotos", action="store_true", help="también sube el espejo de fotos al bucket")
    a = p.parse_args()
    dias = int(os.environ.get("RESPALDO_DIAS", "7"))
    if shutil.which("pg_dump") is None:
        print("Falta pg_dump (corre esto dentro del contenedor 'respaldo').", file=sys.stderr)
        return 2
    if a.comando == "servicio":
        servicio(os.environ.get("RESPALDO_HORA", "02:30"), dias,
                 os.environ.get("RESPALDO_AL_INICIAR", "true").lower() == "true")
    elif a.comando == "respaldar":
        respaldar(dias)
    elif a.comando == "verificar":
        return verificar(a.archivo)
    elif a.comando == "restaurar":
        return restaurar(a.archivo, a.confirmar, a.fotos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
