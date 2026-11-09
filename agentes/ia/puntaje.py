"""Puntaje de una coincidencia candidata (0 a 1) con desglose explicable.

    total = 0.55·vector + 0.25·atributos + 0.12·tiempo + 0.08·zona
    y una penalización ×0.7 si las marcas conocidas se contradicen.

Los pesos y el umbral son el punto de partida; se calibran con el set de evaluación.
"""

from dataclasses import asdict, dataclass

from ia.esquemas import ObjetoNormalizado

PESOS = {"vector": 0.55, "atributos": 0.25, "tiempo": 0.12, "zona": 0.08}
UMBRAL_SUGERENCIA = 0.55
SIMILITUD_PISO = 0.50  # coseno típico entre textos sin relación con bge-m3


@dataclass
class Desglose:
    vector: float
    atributos: float
    tiempo: float
    zona: float
    penalizacion: float
    total: float

    def como_dict(self) -> dict:
        return {k: round(v, 3) for k, v in asdict(self).items()}


def _vector(similitud: float) -> float:
    return max(0.0, min(1.0, (similitud - SIMILITUD_PISO) / (1 - SIMILITUD_PISO)))


def _atributos(a: ObjetoNormalizado, b: ObjetoNormalizado) -> tuple[float, bool]:
    if a.colores and b.colores:
        sa, sb = set(a.colores), set(b.colores)
        color = len(sa & sb) / len(sa | sb)
    else:
        color = 0.5  # desconocido: ni suma ni resta
    if a.marca and b.marca:
        marca_ok = a.marca == b.marca or a.marca in b.marca or b.marca in a.marca
        marca = 1.0 if marca_ok else 0.0
    else:
        marca, marca_ok = 0.5, True
    tipo = 1.0 if a.tipo == b.tipo else 0.3
    return 0.40 * color + 0.35 * marca + 0.25 * tipo, not marca_ok


def _tiempo(dias: int) -> float:
    """dias = fecha_hallazgo - fecha_perdida."""
    if dias < -1:
        return 0.0  # se encontró antes de perderse: casi imposible
    if dias <= 3:
        return 1.0
    if dias <= 30:
        return 1.0 - 0.8 * (dias - 3) / 27
    return 0.1


def _zona(misma_zona: bool | None) -> float:
    return 0.6 if misma_zona is None else (1.0 if misma_zona else 0.4)


def calcular(
    similitud: float,
    perdido: ObjetoNormalizado,
    hallado: ObjetoNormalizado,
    dias: int,
    misma_zona: bool | None,
) -> Desglose:
    v = _vector(similitud)
    at, conflicto_marca = _atributos(perdido, hallado)
    ti = _tiempo(dias)
    zo = _zona(misma_zona)
    pen = 0.7 if conflicto_marca else 1.0
    total = pen * (PESOS["vector"] * v + PESOS["atributos"] * at + PESOS["tiempo"] * ti + PESOS["zona"] * zo)
    return Desglose(v, at, ti, zo, pen, round(total, 4))
