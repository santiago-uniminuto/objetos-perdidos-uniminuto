"""Compara PostgreSQL (una sola instancia) contra Citus con los MISMOS datos sintéticos (Fase 6).

Corre consultas representativas del sistema en los dos motores y mide p50/p95. En Citus además
lee el plan (EXPLAIN) para contar cuántos shards toca cada consulta:

* consultas de UNA sede (portal, matching, bandeja): deben tocar 1 shard ("Task Count: 1").
  Es el beneficio de distribuir por sede_id (ADR-012): cada sede se resuelve en un solo nodo.
* consultas GLOBALES (analítica de todas las sedes): tocan todos los shards en paralelo.

    # En el portátil (desde el contenedor etl, que ya conoce DATABASE_URL y la red de compose):
    docker compose run --rm etl python citus/comparar.py --repeticiones 30

    # Fuera de Docker:
    python datos/citus/comparar.py --postgres postgresql://app:CLAVE@localhost:5432/objetos_perdidos \
        --citus postgresql://citus@localhost:5433/objetos_perdidos --salida pruebas-carga/resultados/citus.md

Ojo al leer los números en un solo portátil: los "nodos" de Citus comparten CPU, disco y RAM, así que
Citus no puede ganar en velocidad bruta; lo que se demuestra es el reparto y el aislamiento por sede.
"""

import argparse
import os
import random
import re
import statistics
import time
from datetime import date, timedelta

import psycopg

CONSULTAS: dict[str, tuple[str, str]] = {
    # nombre: (descripción, SQL con %(sede)s, %(cat)s, %(desde)s, %(hasta)s)
    "portal_sede": (
        "Portal: últimos 25 objetos de una sede",
        "SELECT id, categoria, zona, descripcion_publica, fecha FROM vista_publica_objetos "
        "WHERE sede_id = %(sede)s ORDER BY creado_en DESC, id DESC LIMIT 25"),
    "portal_filtro": (
        "Portal: una sede filtrada por categoría",
        "SELECT id, descripcion_publica, fecha FROM vista_publica_objetos "
        "WHERE sede_id = %(sede)s AND categoria_codigo = %(cod)s ORDER BY creado_en DESC, id DESC LIMIT 25"),
    "matching_candidatos": (
        "Matcher: hallazgos candidatos (sede, categoría, ventana de fechas)",
        "SELECT id, fecha_hallazgo FROM hallazgo WHERE sede_id = %(sede)s AND categoria_id = %(cat)s "
        "AND fecha_hallazgo BETWEEN %(desde)s AND %(hasta)s ORDER BY fecha_hallazgo DESC LIMIT 20"),
    "bandeja_sede": (
        "Admin: coincidencias de una sede con su hallazgo (join co-ubicado)",
        "SELECT co.id, co.puntaje, h.descripcion_publica FROM coincidencia co "
        "JOIN hallazgo h ON (h.id, h.creado_en, h.sede_id) = (co.hallazgo_id, co.hallazgo_creado_en, co.sede_id) "
        "WHERE co.sede_id = %(sede)s ORDER BY co.creado_en DESC LIMIT 50"),
    "global_por_sede_mes": (
        "Analítica global: reportes por sede y mes (todas las sedes)",
        "SELECT sede_id, date_trunc('month', creado_en) AS mes, count(*) FROM reporte_perdida "
        "GROUP BY 1, 2"),
    "global_recuperacion": (
        "Analítica global: tasa de recuperación por categoría (join de 3 tablas)",
        "SELECT r.categoria_id, count(*) AS reportes, count(e.id) AS recuperados FROM reporte_perdida r "
        "LEFT JOIN coincidencia co ON co.reporte_id = r.id AND co.sede_id = r.sede_id AND co.estado = 'entregada' "
        "LEFT JOIN entrega e ON e.coincidencia_id = co.id AND e.sede_id = co.sede_id GROUP BY 1"),
}
CODIGOS = ["electronicos", "documentos", "ropa", "accesorios", "utiles", "llaves", "botellas", "otros"]


def parametros(rnd: random.Random, sedes: list[int]) -> dict:
    d = date.today() - timedelta(days=rnd.randint(30, 600))
    cat = rnd.randint(1, 8)
    return {"sede": rnd.choice(sedes), "cat": cat, "cod": CODIGOS[cat - 1],
            "desde": d - timedelta(days=5), "hasta": d + timedelta(days=45)}


def medir(dsn: str, repeticiones: int, sedes: list[int], semilla: int) -> dict[str, list[float]]:
    tiempos: dict[str, list[float]] = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        for nombre, (_, sql) in CONSULTAS.items():
            rnd = random.Random(semilla)   # mismos parámetros en los dos motores
            for _ in range(3):             # calentamiento: caché de planes y páginas
                conn.execute(sql, parametros(rnd, sedes)).fetchall()
            muestras = []
            for _ in range(repeticiones):
                p = parametros(rnd, sedes)
                t = time.perf_counter()
                conn.execute(sql, p).fetchall()
                muestras.append((time.perf_counter() - t) * 1000)
            tiempos[nombre] = muestras
    return tiempos


def shards_por_consulta(dsn: str, sedes: list[int]) -> dict[str, str]:
    """Lee 'Task Count' del plan de Citus: cuántos shards toca cada consulta."""
    resultado = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        for nombre, (_, sql) in CONSULTAS.items():
            plan = "\n".join(f[0] for f in conn.execute("EXPLAIN " + sql,
                                                        parametros(random.Random(1), sedes)).fetchall())
            tareas = re.findall(r"Task Count: (\d+)", plan)
            resultado[nombre] = "+".join(tareas) if tareas else "coordinador"
    return resultado


def p(muestras: list[float], q: float) -> float:
    return statistics.quantiles(muestras, n=100, method="inclusive")[int(q * 100) - 1]


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")   # separador de miles colombiano


def volumen(dsn: str) -> dict[str, int]:
    with psycopg.connect(dsn) as conn:
        return {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]  # noqa: S608 - nombres fijos
                for t in ("reporte_perdida", "hallazgo", "coincidencia", "entrega")}


def main() -> None:
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--postgres", default=os.environ.get("DATABASE_URL"),
                   help="por defecto DATABASE_URL (dentro del contenedor etl apunta al PostgreSQL del perfil core)")
    a.add_argument("--citus", default="postgresql://citus@citus-coordinador:5432/objetos_perdidos")
    a.add_argument("--repeticiones", type=int, default=30)
    a.add_argument("--sedes", default="1,2,3,4,5,6,7,8,9,10,11,12")
    a.add_argument("--semilla", type=int, default=11)
    a.add_argument("--salida", help="archivo .md donde guardar la tabla")
    args = a.parse_args()
    sedes = [int(s) for s in args.sedes.split(",")]

    vol_pg, vol_ci = volumen(args.postgres), volumen(args.citus)
    pg = medir(args.postgres, args.repeticiones, sedes, args.semilla)
    ci = medir(args.citus, args.repeticiones, sedes, args.semilla)
    tareas = shards_por_consulta(args.citus, sedes)
    with psycopg.connect(args.citus) as conn:
        nodos = conn.execute("SELECT count(*) FROM citus_get_active_worker_nodes()").fetchone()[0]
        shards = conn.execute("SELECT shard_count FROM citus_tables WHERE table_name = 'reporte_perdida'::regclass"
                              ).fetchone()[0]

    lineas = [
        f"# PostgreSQL vs. Citus · {date.today().isoformat()}",
        "",
        f"Datos: {miles(vol_pg['reporte_perdida'])} reportes, {miles(vol_pg['hallazgo'])} hallazgos, "
        f"{miles(vol_pg['coincidencia'])} coincidencias y {miles(vol_pg['entrega'])} entregas en cada motor"
        + ("" if vol_pg == vol_ci else " (Citus tiene otros volúmenes: " +
                                     ", ".join(f"{t} {miles(n)}" for t, n in vol_ci.items()) + ")") + ".",
        f"Citus: {nodos} workers, {shards} shards por tabla. {args.repeticiones} repeticiones por consulta, "
        "con los mismos parámetros en los dos motores.",
        "",
        "| Consulta | PostgreSQL p50 / p95 (ms) | Citus p50 / p95 (ms) | Shards que toca en Citus |",
        "|---|---|---|---|",
    ]
    for nombre, (desc, _) in CONSULTAS.items():
        lineas.append(f"| {desc} | {p(pg[nombre], .5):.1f} / {p(pg[nombre], .95):.1f} "
                      f"| {p(ci[nombre], .5):.1f} / {p(ci[nombre], .95):.1f} | {tareas[nombre]} |")
    texto = "\n".join(lineas) + "\n"
    print(texto)
    if args.salida:
        with open(args.salida, "w", encoding="utf-8") as f:
            f.write(texto)


if __name__ == "__main__":
    main()
