"""Idempotencia de los POST que crean registros (RNF-11).

El cliente manda `Idempotency-Key: <uuid>`. La primera petición guarda su respuesta en
Redis 24 h; si la misma llave llega otra vez (doble clic, reintento por red), se devuelve
la respuesta guardada en lugar de crear un duplicado.
"""

import json
from collections.abc import Callable
from typing import Any

import redis

from app.errores import ErrorApp

TTL = 24 * 3600
PROCESANDO = "__procesando__"


def ejecutar(r: redis.Redis, usuario_id: object, clave: str | None, crear: Callable[[], dict]) -> tuple[dict, bool]:
    """Devuelve (respuesta, es_repetida)."""
    if not clave or len(clave) > 100:
        raise ErrorApp(422, "idempotencia", "Falta el encabezado Idempotency-Key (máx. 100 caracteres)")
    llave = f"idem:{usuario_id}:{clave}"
    if not r.set(llave, PROCESANDO, nx=True, ex=TTL):
        guardada = r.get(llave)
        if guardada == PROCESANDO:
            raise ErrorApp(409, "en_proceso", "Esta misma solicitud todavía se está procesando")
        return json.loads(guardada), True
    try:
        respuesta: dict[str, Any] = crear()
    except Exception:
        r.delete(llave)
        raise
    r.set(llave, json.dumps(respuesta, default=str), ex=TTL)
    return respuesta, False
