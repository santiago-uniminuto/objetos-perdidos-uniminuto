"""Predicción semanal de objetos perdidos con estacionalidad académica (agente analista).

Modelo (deliberadamente simple y explicable):
    λ_t = nivel × factor(clase_t),   y_t ~ Poisson(λ_t)
    clase_t ∈ {vacaciones, inicio (semana 1), parciales (8 y 16), normal}

- factor(clase) = media de las semanas de esa clase / media de las semanas normales (histórico).
- nivel = media de y_t / factor(clase_t) en las últimas `VENTANA_NIVEL` semanas (sigue la tendencia).
- Intervalo del 90 %: cuantiles 5 % y 95 % de la Poisson.

Se compara contra una línea base ingenua (media de las últimas 4 semanas) con un backtest de
un paso hacia adelante: si el modelo no le gana a la ingenua, el informe lo dice.
Todo es aritmética en código; el LLM nunca calcula, solo redacta con estos números.
"""

import math
from dataclasses import dataclass
from datetime import date

VENTANA_NIVEL = 8
VENTANA_INGENUA = 4
MIN_HISTORIA = 12  # semanas mínimas para estimar factores


@dataclass(frozen=True)
class Semana:
    inicio: date
    semana_semestre: int | None
    es_parciales: bool

    @property
    def clase(self) -> str:
        if self.semana_semestre is None:
            return "vacaciones"
        if self.es_parciales:
            return "parciales"
        return "inicio" if self.semana_semestre == 1 else "normal"


def factores(semanas: list[Semana], y: list[float]) -> dict[str, float]:
    sumas: dict[str, list[float]] = {}
    for s, v in zip(semanas, y, strict=True):
        sumas.setdefault(s.clase, []).append(v)
    medias = {c: sum(v) / len(v) for c, v in sumas.items()}
    base = medias.get("normal") or (sum(y) / len(y) if y else 1.0) or 1.0
    f = {c: m / base for c, m in medias.items()}
    f["normal"] = 1.0
    for c, defecto in (("vacaciones", 0.2), ("inicio", 1.0), ("parciales", 1.0)):
        f.setdefault(c, defecto)  # clase nunca vista: valor prudente
    return {c: max(v, 0.01) for c, v in f.items()}


def nivel(semanas: list[Semana], y: list[float], f: dict[str, float]) -> float:
    ult = list(zip(semanas, y, strict=True))[-VENTANA_NIVEL:]
    return sum(v / f[s.clase] for s, v in ult) / len(ult) if ult else 0.0


def cuantil_poisson(lam: float, p: float) -> int:
    if lam <= 0:
        return 0
    if lam > 60:  # aproximación normal (la exacta se desborda con λ grande)
        z = {0.05: -1.6449, 0.95: 1.6449}[p]
        return max(0, round(lam + z * math.sqrt(lam)))
    k, acumulada, termino = 0, math.exp(-lam), math.exp(-lam)
    while acumulada < p:
        k += 1
        termino *= lam / k
        acumulada += termino
    return k


def pronosticar(historia: list[Semana], y: list[float], futuras: list[Semana]) -> list[dict]:
    f = factores(historia, y)
    n = nivel(historia, y, f)
    salida = []
    for s in futuras:
        lam = n * f[s.clase]
        salida.append({"semana_inicio": s.inicio.isoformat(), "clase": s.clase, "esperado": round(lam, 1),
                       "minimo_90": cuantil_poisson(lam, 0.05), "maximo_90": cuantil_poisson(lam, 0.95)})
    return salida


def backtest(historia: list[Semana], y: list[float], semanas_prueba: int = 12) -> dict | None:
    """Error absoluto medio de un paso hacia adelante: modelo vs. ingenua (media de 4 semanas)."""
    if len(y) < MIN_HISTORIA + semanas_prueba:
        return None
    err_m, err_i = [], []
    for k in range(len(y) - semanas_prueba, len(y)):
        hist, yy = historia[:k], y[:k]
        f = factores(hist, yy)
        pred_m = nivel(hist, yy, f) * f[historia[k].clase]
        pred_i = sum(yy[-VENTANA_INGENUA:]) / VENTANA_INGENUA
        err_m.append(abs(y[k] - pred_m))
        err_i.append(abs(y[k] - pred_i))
    mae_m, mae_i = sum(err_m) / len(err_m), sum(err_i) / len(err_i)
    return {"semanas_evaluadas": semanas_prueba, "mae_modelo": round(mae_m, 1), "mae_ingenuo": round(mae_i, 1),
            "mejora_pct": round(100 * (1 - mae_m / mae_i), 1) if mae_i else 0.0,
            "gana_modelo": mae_m < mae_i}
