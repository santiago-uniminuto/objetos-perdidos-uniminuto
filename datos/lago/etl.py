"""ETL: outbox de PostgreSQL → MongoDB (`eventos`) + capa bronze del lake (ADR-004, ADR-014).

Es un consumidor más del outbox ('etl' en consumidor_outbox), igual que los agentes.
Cada lote se escribe como un archivo Parquet nuevo en bronze/eventos/fecha=AAAA-MM-DD/.
Cada TRANSFORMAR_MINUTOS reconstruye silver y gold.

    python -m lago.etl            # bucle continuo (servicio `etl`)
    python -m lago.etl --una-vez  # procesa lo pendiente, transforma y termina
"""

import argparse
import json
import logging
import os
import time

import psycopg
import pyarrow as pa
from psycopg.rows import dict_row

from lago.almacen import Lago

log = logging.getLogger("etl")
LOTE = int(os.environ.get("ETL_LOTE", "5000"))

ESQUEMA_BRONZE = pa.schema([
    ("outbox_id", pa.int64()), ("creado_en", pa.timestamp("us", tz="UTC")), ("agregado", pa.string()),
    ("agregado_id", pa.string()), ("sede_id", pa.int16()), ("tipo_evento", pa.string()), ("payload", pa.string()),
])


def procesar_lote(conn: psycopg.Connection, lago: Lago, eventos_mongo=None, limite: int = LOTE) -> int:
    """Lleva hasta `limite` eventos nuevos a bronze (y a Mongo). Devuelve cuántos procesó."""
    ultimo = conn.execute("SELECT ultimo_id FROM consumidor_outbox WHERE consumidor = 'etl'").fetchone()["ultimo_id"]
    filas = conn.execute(
        "SELECT id, creado_en, agregado, agregado_id::text AS agregado_id, sede_id, tipo_evento, payload "
        "FROM outbox WHERE id > %s ORDER BY id LIMIT %s", (ultimo, limite),
    ).fetchall()
    if not filas:
        return 0

    # Una partición bronze por día del evento
    por_dia: dict[str, list[dict]] = {}
    for f in filas:
        por_dia.setdefault(f["creado_en"].date().isoformat(), []).append(f)
    for dia, grupo in por_dia.items():
        tabla = pa.Table.from_pylist(
            [{"outbox_id": g["id"], "creado_en": g["creado_en"], "agregado": g["agregado"],
              "agregado_id": g["agregado_id"], "sede_id": g["sede_id"], "tipo_evento": g["tipo_evento"],
              "payload": json.dumps(g["payload"], ensure_ascii=False)} for g in grupo],
            schema=ESQUEMA_BRONZE)
        lago.agregar(f"bronze/eventos/fecha={dia}", tabla)

    if eventos_mongo is not None:
        _copiar_a_mongo(eventos_mongo, filas)

    # El offset avanza solo después de escribir: si algo falla, el lote se repite (al menos una vez).
    # Bronze puede quedar con duplicados; silver los elimina por outbox_id.
    with conn.transaction():
        conn.execute("UPDATE consumidor_outbox SET ultimo_id = %s, actualizado_en = now() WHERE consumidor = 'etl'",
                     (filas[-1]["id"],))
    return len(filas)


def _copiar_a_mongo(coleccion, filas: list[dict]) -> None:
    from pymongo.errors import BulkWriteError

    docs = [{"outbox_id": f["id"], "creado_en": f["creado_en"], "agregado": f["agregado"],
             "agregado_id": f["agregado_id"], "sede_id": f["sede_id"], "tipo_evento": f["tipo_evento"],
             "payload": f["payload"]} for f in filas]
    try:
        coleccion.insert_many(docs, ordered=False)
    except BulkWriteError as exc:  # duplicados por reproceso: el índice único de outbox_id los descarta
        if any(e.get("code") != 11000 for e in exc.details.get("writeErrors", [])):
            raise


def main() -> None:
    from lago.transformar import transformar

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--una-vez", action="store_true")
    a = p.parse_args()

    conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, row_factory=dict_row)
    lago = Lago.desde_entorno()
    mongo = None
    if os.environ.get("MONGO_URL") and os.environ.get("ETL_COPIAR_MONGO", "true").lower() == "true":
        import pymongo

        mongo = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ.get("MONGO_DB", "objetos_perdidos")]["eventos"]
    cada = float(os.environ.get("ETL_TRANSFORMAR_MINUTOS", "15")) * 60
    ultima_transformacion = 0.0
    while True:
        n = procesar_lote(conn, lago, mongo)
        if n:
            log.info("bronze: %s eventos", n)
        if (a.una_vez and n == 0) or time.time() - ultima_transformacion > cada:
            compactadas = lago.compactar("bronze/eventos")
            resumen = transformar(lago, conn)
            resumen["particiones_compactadas"] = compactadas
            log.info("silver/gold reconstruidas: %s", resumen)
            ultima_transformacion = time.time()
            if a.una_vez and n == 0:
                break
        if n == 0:
            time.sleep(float(os.environ.get("ETL_INTERVALO", "5")))


if __name__ == "__main__":
    main()
