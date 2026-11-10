"""Worker de agentes: consume el outbox de PostgreSQL (ADR-014).

Cada consumidor (matcher, notificador) guarda su último evento procesado en
`consumidor_outbox`. Garantía "al menos una vez": si el worker se cae a mitad de un
evento, lo reprocesa al volver; por eso los agentes son idempotentes.
Un lock en Redis evita que dos copias del worker procesen el mismo consumidor.

    python -m harness.worker              # bucle continuo (contenedor `agentes`)
    python -m harness.worker --una-vez    # procesa lo pendiente y termina
"""

import argparse
import logging
import socket
import time
import uuid
from collections.abc import Callable

import psycopg
import redis
from psycopg.rows import dict_row

from harness.config import Config
from harness.correo import EnviadorSMTP
from harness.matcher import Matcher
from harness.notificador import Notificador
from harness.nucleo import RegistroTrazas

log = logging.getLogger("worker")

SUSCRIPCIONES = {
    "matcher": {"reporte.creado", "hallazgo.creado"},
    "notificador": {"coincidencia.verificada"},
}
MAX_INTENTOS = 3
LOTE = 20
TTL_LOCK = 300  # el matcher puede tardar ~2 min por evento con el LLM


def procesar_lote(conn: psycopg.Connection, r: redis.Redis, consumidor: str,
                  manejar: Callable[[dict], object], dueno: str, limite: int = LOTE) -> int:
    """Procesa hasta `limite` eventos nuevos para un consumidor. Devuelve cuántos avanzó."""
    llave_lock = f"lock:consumidor:{consumidor}"
    if not r.set(llave_lock, dueno, nx=True, ex=TTL_LOCK) and r.get(llave_lock) != dueno:
        return 0  # otra copia del worker tiene este consumidor
    r.expire(llave_lock, TTL_LOCK)

    ultimo = conn.execute("SELECT ultimo_id FROM consumidor_outbox WHERE consumidor = %s",
                          (consumidor,)).fetchone()["ultimo_id"]
    eventos = conn.execute(
        "SELECT id, agregado, agregado_id, sede_id, tipo_evento, payload FROM outbox "
        "WHERE id > %s ORDER BY id LIMIT %s",
        (ultimo, limite),
    ).fetchall()
    avanzados = 0
    for ev in eventos:
        r.expire(llave_lock, TTL_LOCK)  # renueva el lock en cada evento
        if ev["tipo_evento"] in SUSCRIPCIONES[consumidor]:
            intentos_llave = f"intentos:{consumidor}:{ev['id']}"
            try:
                manejar(ev)
                r.delete(intentos_llave)
            except Exception as exc:
                intentos = r.incr(intentos_llave)
                r.expire(intentos_llave, 86400)
                if intentos < MAX_INTENTOS:
                    log.warning("%s falló en el evento %s (intento %s): %s", consumidor, ev["id"], intentos,
                                type(exc).__name__)
                    break  # se reintenta en la próxima vuelta, sin saltarse el orden
                log.error("%s descarta el evento %s tras %s intentos", consumidor, ev["id"], intentos)
        with conn.transaction():
            conn.execute("UPDATE consumidor_outbox SET ultimo_id = %s, actualizado_en = now() WHERE consumidor = %s",
                         (ev["id"], consumidor))
        avanzados += 1
    return avanzados


def construir(cfg: Config):
    """Conexiones y agentes reales (Postgres, Redis, Mongo, Ollama, SMTP)."""
    from ia.proveedores import ChatProvider, EmbeddingProvider

    conn = psycopg.connect(cfg.database_url, autocommit=True, row_factory=dict_row)
    r = redis.Redis.from_url(cfg.redis_url, decode_responses=True)
    coleccion = None
    if cfg.mongo_url:
        import pymongo

        coleccion = pymongo.MongoClient(cfg.mongo_url, serverSelectionTimeoutMS=3000)[cfg.mongo_db]["trazas_agente"]
    trazas = RegistroTrazas(coleccion)
    chat = ChatProvider.desde_entorno() if cfg.normalizador == "llm" or cfg.explicar else None
    matcher = Matcher(trazas, conn, chat, EmbeddingProvider.desde_entorno(), cfg.normalizador, cfg.explicar)
    notificador = Notificador(trazas, conn, r, EnviadorSMTP(cfg))
    return conn, r, {"matcher": matcher.ejecutar, "notificador": notificador.ejecutar}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser()
    p.add_argument("--una-vez", action="store_true")
    a = p.parse_args()
    cfg = Config()
    conn, r, manejadores = construir(cfg)
    dueno = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
    log.info("worker %s listo: %s", dueno, ", ".join(manejadores))
    while True:
        total = sum(procesar_lote(conn, r, nombre, fn, dueno) for nombre, fn in manejadores.items())
        if a.una_vez and total == 0:
            break
        if total == 0:
            time.sleep(cfg.intervalo_segundos)


if __name__ == "__main__":
    main()
