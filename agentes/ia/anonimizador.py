"""Quita datos personales del texto antes de enviarlo a cualquier modelo (ADR-006).

Devuelve el texto limpio y la lista de TIPOS eliminados (nunca los valores),
que es lo que se guarda en la traza del agente.
"""

import re
import unicodedata
from dataclasses import dataclass, field

_CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Celular colombiano: 3xx xxx xxxx (con o sin espacios/guiones, opcional +57)
_TELEFONO = re.compile(r"(?:\+?57[\s-]?)?\b3\d{2}[\s-]?\d{3}[\s-]?\d{4}\b")
# Documento: 6 a 10 dígitos, o con puntos de miles (1.234.567.890)
_DOCUMENTO = re.compile(r"\b\d{1,3}(?:\.\d{3}){2,3}\b|\b\d{6,10}\b")
# "me llamo Ana", "mi nombre es Ana María Gómez", "pertenece a Juan Pérez".
# No se usa "es de ...": atraparía marcas ("es de Stanley") y ciudades.
_PRESENTACION = re.compile(
    r"\b((?i:me llamo|mi nombre es|propiedad de|pertenece a|a nombre de))\s+"
    r"((?:[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){0,3})"
)


@dataclass
class Resultado:
    texto: str
    eliminados: list[str] = field(default_factory=list)


def _sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def anonimizar(texto: str, nombres_conocidos: list[str] | None = None) -> Resultado:
    """Reemplaza correos, teléfonos, documentos y nombres por marcadores."""
    eliminados: list[str] = []

    def sub(patron: re.Pattern, marcador: str, t: str, tipo: str) -> str:
        nuevo, n = patron.subn(marcador, t)
        if n:
            eliminados.append(tipo)
        return nuevo

    t = sub(_CORREO, "[CORREO]", texto, "correo")
    t = sub(_TELEFONO, "[TELEFONO]", t, "telefono")
    t = sub(_DOCUMENTO, "[DOCUMENTO]", t, "documento")

    t, n = _PRESENTACION.subn(lambda m: f"{m.group(1)} [NOMBRE]", t)
    if n:
        eliminados.append("nombre")

    # Nombres y apellidos registrados del dueño, sin importar mayúsculas ni tildes
    for nombre in nombres_conocidos or []:
        for parte in nombre.split():
            if len(parte) < 3:
                continue
            patron = re.compile(rf"\b{re.escape(_sin_tildes(parte))}\b", re.IGNORECASE)
            base = _sin_tildes(t)
            posiciones = [m.span() for m in patron.finditer(base)]
            if posiciones:
                # _sin_tildes conserva la longitud de los caracteres latinos más comunes
                for ini, fin in reversed(posiciones):
                    t = t[:ini] + "[NOMBRE]" + t[fin:]
                if "nombre" not in eliminados:
                    eliminados.append("nombre")

    return Resultado(texto=t, eliminados=eliminados)
