"""Esquemas de salida del LLM. Todo lo que devuelve un modelo se valida aquí."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Categoria = Literal["electronicos", "documentos", "ropa", "accesorios", "utiles", "llaves", "botellas", "otros"]

# Vocabulario cerrado de colores: los sinónimos se llevan a una forma canónica.
SINONIMOS_COLOR = {
    "azul oscuro": "azul", "azul marino": "azul", "azul claro": "azul", "celeste": "azul",
    "turquesa": "azul", "negra": "negro", "blanca": "blanco", "roja": "rojo", "vinotinto": "rojo",
    "morada": "morado", "lila": "morado", "violeta": "morado", "amarilla": "amarillo",
    "plateado": "gris", "plateada": "gris", "plata": "gris", "grises": "gris",
    "dorado": "dorado", "dorada": "dorado", "cafe": "café", "marrón": "café", "marron": "café",
    "beige": "beige", "crema": "beige", "rosada": "rosado", "fucsia": "rosado", "verde oscuro": "verde",
    "verde claro": "verde", "verde militar": "verde",
}
COLORES = {"azul", "negro", "blanco", "rojo", "verde", "amarillo", "morado", "gris", "dorado",
           "café", "beige", "rosado", "naranja", "transparente"}


def canonizar_color(c: str) -> str | None:
    c = c.strip().lower()
    c = SINONIMOS_COLOR.get(c, c)
    return c if c in COLORES else None


class ObjetoNormalizado(BaseModel):
    """Salida del agente normalizador (también la produce la heurística sin LLM)."""

    categoria: Categoria
    tipo: str = Field(min_length=1, max_length=40, description="sustantivo principal: termo, celular, chaqueta")
    marca: str | None = Field(default=None, max_length=40)
    colores: list[str] = Field(default_factory=list, max_length=3)
    material: str | None = Field(default=None, max_length=30)
    rasgos: list[str] = Field(default_factory=list, max_length=5, description="detalles visibles distintivos")
    resumen: str = Field(max_length=160)

    @field_validator("tipo", "marca", "material", mode="before")
    @classmethod
    def _minusculas(cls, v):
        if isinstance(v, str):
            return v.strip().lower() or None
        return v

    @field_validator("colores", mode="before")
    @classmethod
    def _colores(cls, v):
        vistos: list[str] = []
        for c in v or []:
            canon = canonizar_color(str(c))
            if canon and canon not in vistos:
                vistos.append(canon)
        return vistos[:3]

    @field_validator("rasgos", mode="before")
    @classmethod
    def _rasgos(cls, v):
        return [str(r).strip().lower()[:60] for r in (v or []) if str(r).strip()][:5]


class Explicacion(BaseModel):
    """Salida del agente explicador para un par reporte–hallazgo."""

    coincide_en: list[str] = Field(default_factory=list, max_length=4)
    difiere_en: list[str] = Field(default_factory=list, max_length=4)
    explicacion: str = Field(max_length=400)
    confianza: Literal["alta", "media", "baja"]


def texto_canonico(o: ObjetoNormalizado) -> str:
    """Texto que se vectoriza: mismo orden y vocabulario para reportes y hallazgos."""
    partes = [o.categoria, o.tipo]
    if o.marca:
        partes.append(f"marca {o.marca}")
    if o.colores:
        partes.append("color " + " ".join(o.colores))
    if o.material:
        partes.append(f"material {o.material}")
    if o.rasgos:
        partes.append("rasgos " + "; ".join(o.rasgos))
    return " | ".join(partes)
