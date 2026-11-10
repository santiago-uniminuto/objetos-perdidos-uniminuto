"""Redis: caché de la vista pública, límite de peticiones e idempotencia."""

import redis

from app.config import get_settings

_cliente: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _cliente
    if _cliente is None:
        _cliente = redis.Redis.from_url(get_settings().redis_url, decode_responses=True, socket_timeout=2)
    return _cliente
