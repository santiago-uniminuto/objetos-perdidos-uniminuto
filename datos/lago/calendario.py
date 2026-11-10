"""Calendario académico para la serie semanal y la predicción de picos.

SUPUESTO (Fase 4): semestres de 18 semanas con parciales en las semanas 8 y 16.
Las fechas de inicio son aproximadas; reemplázalas por el calendario oficial de la sede
cuando el grupo lo consiga. Las semanas fuera de un semestre son vacaciones.
"""

from datetime import date, timedelta

INICIOS_SEMESTRE = [date(2024, 1, 29), date(2024, 7, 29), date(2025, 2, 3), date(2025, 7, 28),
                    date(2026, 2, 2), date(2026, 7, 27), date(2027, 2, 1)]
SEMANAS = 18
PARCIALES = {8, 16}


def lunes(d: date) -> date:
    return d - timedelta(days=d.weekday())


def semana_semestre(d: date) -> int | None:
    """1..18 si la fecha cae en un semestre, None en vacaciones."""
    for inicio in INICIOS_SEMESTRE:
        n = (lunes(d) - lunes(inicio)).days // 7 + 1
        if 1 <= n <= SEMANAS:
            return n
    return None


def es_parciales(d: date) -> bool:
    return semana_semestre(d) in PARCIALES


def tabla_semanas(desde: date, hasta: date) -> list[dict]:
    """Una fila por lunes entre las dos fechas, con la semana del semestre."""
    filas, s = [], lunes(desde)
    while s <= hasta:
        n = semana_semestre(s)
        filas.append({"semana_inicio": s, "semana_semestre": n, "es_parciales": n in PARCIALES})
        s += timedelta(days=7)
    return filas
