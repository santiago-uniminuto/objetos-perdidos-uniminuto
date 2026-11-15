"""Convierte los CSV de Locust en una tabla markdown lista para el artículo (Fase 6).

    python pruebas-carga/resumir.py pruebas-carga/resultados/base "100 usuarios, 3 min, caché caliente"

Lee <prefijo>_stats.csv (lo genera `locust --csv <prefijo>`) y escribe <prefijo>.md.
"""

import csv
import sys
from pathlib import Path

META_P95_MS = 300


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    prefijo = Path(sys.argv[1])
    escenario = sys.argv[2] if len(sys.argv) > 2 else ""
    with open(f"{prefijo}_stats.csv", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))

    total = next(f for f in filas if f["Name"] == "Aggregated")
    rutas = sorted((f for f in filas if f["Name"] != "Aggregated"), key=lambda f: -int(f["Request Count"]))
    n, fallas = int(total["Request Count"]), int(total["Failure Count"])
    publicas = [f for f in rutas if f["Name"].startswith("publico:")]
    peor_p95 = max((float(f["95%"]) for f in publicas), default=0.0)

    lineas = [
        f"# Prueba de carga · {prefijo.name}",
        "",
        f"Escenario: {escenario}" if escenario else "",
        f"Total: {n:,} peticiones · **{float(total['Requests/s']):.1f} peticiones/s** · "
        f"errores {fallas / n:.2%} · p95 global {float(total['95%']):.0f} ms".replace(",", "."),
        f"Lectura pública (RNF-01, meta p95 < {META_P95_MS} ms): peor ruta {peor_p95:.0f} ms → "
        + ("**cumple**" if peor_p95 < META_P95_MS else "**no cumple**"),
        "",
        "| Ruta | Peticiones | Peticiones/s | p50 (ms) | p95 (ms) | p99 (ms) | Errores |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for f in rutas:
        lineas.append(f"| {f['Name']} | {int(f['Request Count'])} | {float(f['Requests/s']):.1f} | {f['50%']} "
                      f"| {f['95%']} | {f['99%']} | {f['Failure Count']} |")
    salida = prefijo.with_suffix(".md")
    salida.write_text("\n".join(x for x in lineas if x is not None) + "\n", encoding="utf-8")
    print(salida.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
