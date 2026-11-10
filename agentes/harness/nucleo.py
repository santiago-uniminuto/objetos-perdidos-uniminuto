"""Núcleo del harness.

Cada ejecución de un agente:
- solo puede usar las herramientas que tiene permitidas (permiso explícito por agente);
- tiene un presupuesto de llamadas al LLM, tokens y segundos; si lo supera, se corta;
- deja una traza con cada paso (herramienta, resumen de entrada/salida, ms, éxito),
  los TIPOS de datos personales eliminados (nunca los valores), tokens y estado.
"""

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from ia.proveedores import Uso

log = logging.getLogger("harness")


class LimiteExcedido(Exception):
    """El agente superó su presupuesto de llamadas, tokens o tiempo."""


class HerramientaNoPermitida(Exception):
    """El agente intentó usar una herramienta que no tiene asignada."""


@dataclass(frozen=True)
class Limites:
    max_llamadas_llm: int
    max_tokens: int
    max_segundos: float


def _resumen(valor: Any, largo: int = 160) -> str:
    texto = str(valor)
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


@dataclass
class Ejecucion:
    agente: str
    disparador: dict
    limites: Limites
    proveedor: str | None = None
    modelo: str | None = None
    ejecucion_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    inicio: float = field(default_factory=time.perf_counter)
    pasos: list[dict] = field(default_factory=list)
    llamadas_llm: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0
    datos_eliminados: list[str] = field(default_factory=list)
    respaldo: bool = False  # se usó un plan B (p. ej. heurística porque el LLM falló)

    def registrar_llm(self, uso: Uso) -> None:
        self.llamadas_llm += 1
        self.tokens_entrada += uso.tokens_entrada
        self.tokens_salida += uso.tokens_salida
        if self.llamadas_llm > self.limites.max_llamadas_llm:
            raise LimiteExcedido(f"más de {self.limites.max_llamadas_llm} llamadas al LLM")
        if self.tokens_entrada + self.tokens_salida > self.limites.max_tokens:
            raise LimiteExcedido(f"más de {self.limites.max_tokens} tokens")

    def verificar_tiempo(self) -> None:
        if time.perf_counter() - self.inicio > self.limites.max_segundos:
            raise LimiteExcedido(f"más de {self.limites.max_segundos} s")

    def documento(self, estado: str, salida: Any = None, error: str | None = None) -> dict:
        """Documento para la colección trazas_agente (validada en Mongo)."""
        return {
            "ejecucion_id": self.ejecucion_id, "agente": self.agente, "disparador": self.disparador,
            "proveedor": self.proveedor or "ninguno", "modelo": self.modelo or "ninguno", "pasos": self.pasos,
            "salida": salida, "tokens": {"entrada": self.tokens_entrada, "salida": self.tokens_salida},
            "llamadas_llm": self.llamadas_llm, "datos_personales_eliminados": sorted(set(self.datos_eliminados)),
            "latencia_ms": round((time.perf_counter() - self.inicio) * 1000, 1), "estado": estado,
            **({"error": error} if error else {}), "creado_en": datetime.now(UTC),
        }


class Agente:
    """Base de los agentes: cada subclase declara su nombre, límites y herramientas permitidas."""

    nombre: str = "agente"
    limites: Limites = Limites(max_llamadas_llm=0, max_tokens=0, max_segundos=30)
    herramientas_permitidas: frozenset[str] = frozenset()

    def __init__(self, trazas: "RegistroTrazas"):
        self.trazas = trazas
        self.ejecucion: Ejecucion | None = None

    def usar(self, herramienta: str, fn: Callable[..., Any], *args, entrada: Any = None, sensible: bool = False,
             **kwargs) -> Any:
        """Ejecuta una herramienta dentro del presupuesto y deja el paso en la traza.

        `sensible=True` para herramientas que devuelven datos personales: la traza guarda
        que el paso ocurrió, pero no su resultado."""
        if herramienta not in self.herramientas_permitidas:
            raise HerramientaNoPermitida(f"{self.nombre} no puede usar '{herramienta}'")
        assert self.ejecucion is not None
        self.ejecucion.verificar_tiempo()
        inicio = time.perf_counter()
        paso = {"herramienta": herramienta, "entrada_resumen": _resumen(entrada if entrada is not None else args)}
        try:
            resultado = fn(*args, **kwargs)
            paso.update(ok=True, salida_resumen="(datos personales omitidos)" if sensible else _resumen(resultado))
            return resultado
        except Exception as exc:
            paso.update(ok=False, salida_resumen=type(exc).__name__)
            raise
        finally:
            paso["ms"] = round((time.perf_counter() - inicio) * 1000, 1)
            self.ejecucion.pasos.append(paso)

    def ejecutar(self, evento: dict) -> dict:
        """Envuelve `manejar` con la traza. Devuelve el documento de traza."""
        self.ejecucion = Ejecucion(self.nombre, {"tipo": evento["tipo_evento"], "ref": str(evento["agregado_id"]),
                                                 "outbox_id": evento["id"]}, self.limites)
        try:
            salida = self.manejar(evento)
            doc = self.ejecucion.documento("respaldo" if self.ejecucion.respaldo else "ok", salida)
        except LimiteExcedido as exc:
            doc = self.ejecucion.documento("limite_excedido", error=str(exc))
        except Exception as exc:
            doc = self.ejecucion.documento("error", error=f"{type(exc).__name__}: {_resumen(exc, 300)}")
            self.trazas.guardar(doc)
            raise
        self.trazas.guardar(doc)
        return doc

    def manejar(self, evento: dict) -> Any:  # pragma: no cover - lo implementa cada agente
        raise NotImplementedError


class RegistroTrazas:
    """Guarda las trazas en MongoDB; si Mongo no está disponible, las deja en el log (no detiene al agente)."""

    def __init__(self, coleccion=None):
        self.coleccion = coleccion

    def guardar(self, doc: dict) -> None:
        if self.coleccion is None:
            log.info("traza %s %s %s", doc["agente"], doc["estado"], doc["ejecucion_id"])
            return
        try:
            self.coleccion.insert_one(dict(doc))
        except Exception as exc:  # noqa: BLE001 - la traza nunca debe tumbar al agente
            # Las trazas no llevan datos personales, así que el detalle del validador se puede registrar
            detalle = getattr(exc, "details", None) or {}
            log.warning("no se pudo guardar la traza en Mongo: %s %s %s", type(exc).__name__,
                        detalle.get("code", ""), _resumen(detalle.get("errInfo", detalle.get("errmsg", "")), 400))
