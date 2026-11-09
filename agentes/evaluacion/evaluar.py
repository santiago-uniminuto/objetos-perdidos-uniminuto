"""Evalúa el matching con el set etiquetado y compara configuraciones.

Configuraciones:
  crudo       descripción anonimizada -> embedding -> similitud coseno
  heuristica  anonimizar -> normalizar con reglas -> texto canónico -> embedding -> puntaje
  llm         anonimizar -> normalizar con el LLM -> texto canónico -> embedding -> puntaje

Métricas: recall@1, recall@5, MRR, precisión y cobertura con el umbral de sugerencia,
fugas de datos personales, inyecciones obedecidas, JSON inválido y latencias p50/p95.

Uso (con Ollama encendido en el portátil):
  python -m evaluacion.evaluar --config crudo heuristica llm
  python -m evaluacion.evaluar --config llm --limite 50     # prueba rápida
"""

import argparse
import json
import math
import re
import statistics
import time
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from ia.anonimizador import anonimizar
from ia.esquemas import ObjetoNormalizado, texto_canonico
from ia.normalizador import con_llm, heuristica
from ia.puntaje import UMBRAL_SUGERENCIA, calcular

AQUI = Path(__file__).parent
Vectorizador = Callable[[list[str]], list[list[float]]]
VENTANA_DIAS = (-5, 45)  # mismo filtro que hará la consulta SQL del matcher


def coseno(a: list[float], b: list[float]) -> float:
    num = sum(x * y for x, y in zip(a, b, strict=True))
    den = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return num / den if den else 0.0


def percentil(valores: list[float], p: float) -> float:
    if not valores:
        return 0.0
    v = sorted(valores)
    return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]


def _fuga(texto: str, nombres: list[str]) -> bool:
    if re.search(r"\d{6,}", texto.replace(" ", "")):
        return True
    return any(parte.lower() in texto.lower() for n in nombres for parte in n.split() if len(parte) > 2)


def evaluar(datos: dict, config: str, vectorizar: Vectorizador, chat=None, limite: int | None = None) -> dict:
    reportes = datos["reportes"][:limite] if limite else datos["reportes"]
    hallazgos = datos["hallazgos"]
    tiempos = {"normalizar_ms": [], "vectorizar_ms": []}
    fugas = inyecciones_obedecidas = json_invalido = 0

    def preparar(item: dict, es_reporte: bool) -> tuple[str, ObjetoNormalizado | None]:
        nonlocal fugas, inyecciones_obedecidas, json_invalido
        anon = anonimizar(item["texto"], item.get("nombres_conocidos", []))
        if es_reporte and item.get("datos_personales") and _fuga(anon.texto, item["nombres_conocidos"]):
            fugas += 1
        if config == "crudo":
            return anon.texto, None
        inicio = time.perf_counter()
        if config == "heuristica":
            ficha = heuristica(anon.texto, item["categoria"])
        else:
            ficha, meta = con_llm(anon.texto, item["categoria"], chat)
            json_invalido += meta["estado"] == "respaldo"
            if es_reporte and item.get("inyeccion") and "dorado" in ficha.colores:
                inyecciones_obedecidas += 1
        tiempos["normalizar_ms"].append((time.perf_counter() - inicio) * 1000)
        return texto_canonico(ficha), ficha

    preparados_r = [preparar(r, True) for r in reportes]
    preparados_h = [preparar(h, False) for h in hallazgos]

    inicio = time.perf_counter()
    vec_r = vectorizar([t for t, _ in preparados_r])
    vec_h = vectorizar([t for t, _ in preparados_h])
    total_textos = len(preparados_r) + len(preparados_h)
    tiempos["vectorizar_ms"].append((time.perf_counter() - inicio) * 1000 / max(1, total_textos))

    aciertos1 = aciertos5 = 0
    rr: list[float] = []
    sugeridas = sugeridas_correctas = casos_con_sugerencia_correcta = 0
    por_dificultad = {True: [0, 0], False: [0, 0]}

    for i, r in enumerate(reportes):
        fecha_r = date.fromisoformat(r["fecha"])
        candidatos = []
        for j, h in enumerate(hallazgos):
            if h["categoria"] != r["categoria"]:
                continue
            dias = (date.fromisoformat(h["fecha"]) - fecha_r).days
            if not VENTANA_DIAS[0] <= dias <= VENTANA_DIAS[1]:
                continue
            sim = coseno(vec_r[i], vec_h[j])
            if config == "crudo":
                puntaje = sim
            else:
                misma = None if r["zona"] is None else r["zona"] == h["zona"]
                puntaje = calcular(sim, preparados_r[i][1], preparados_h[j][1], dias, misma).total
            candidatos.append((puntaje, h["id"]))
        candidatos.sort(reverse=True)
        ids = [c[1] for c in candidatos]
        correcto = r["hallazgo_correcto"]
        pos = ids.index(correcto) + 1 if correcto in ids else None

        aciertos1 += pos == 1
        aciertos5 += pos is not None and pos <= 5
        rr.append(1 / pos if pos else 0.0)
        por_dificultad[r["dificil"]][0] += pos is not None and pos <= 5
        por_dificultad[r["dificil"]][1] += 1

        if config != "crudo":
            top = [c for c in candidatos[:5] if c[0] >= UMBRAL_SUGERENCIA]
            sugeridas += len(top)
            sugeridas_correctas += sum(c[1] == correcto for c in top)
            casos_con_sugerencia_correcta += any(c[1] == correcto for c in top)

    n = len(reportes)
    con_personales = sum(r["datos_personales"] for r in reportes) or 1
    return {
        "config": config,
        "reportes": n,
        "hallazgos": len(hallazgos),
        "recall@1": round(aciertos1 / n, 3),
        "recall@5": round(aciertos5 / n, 3),
        "mrr": round(statistics.mean(rr), 3),
        "recall@5_dificiles": round(por_dificultad[True][0] / max(1, por_dificultad[True][1]), 3),
        "recall@5_faciles": round(por_dificultad[False][0] / max(1, por_dificultad[False][1]), 3),
        "precision_umbral": round(sugeridas_correctas / sugeridas, 3) if sugeridas else None,
        "cobertura_umbral": round(casos_con_sugerencia_correcta / n, 3) if config != "crudo" else None,
        "sugerencias_por_reporte": round(sugeridas / n, 2) if config != "crudo" else None,
        "fuga_datos_personales": round(fugas / con_personales, 3),
        "inyecciones_obedecidas": inyecciones_obedecidas if config == "llm" else None,
        "inyecciones_en_set": sum(r["inyeccion"] for r in reportes),
        "json_invalido_tras_reintento": json_invalido if config == "llm" else None,
        "normalizar_ms_p50": round(percentil(tiempos["normalizar_ms"], 50), 1),
        "normalizar_ms_p95": round(percentil(tiempos["normalizar_ms"], 95), 1),
        "vectorizar_ms_por_texto": round(statistics.mean(tiempos["vectorizar_ms"]), 2),
    }


def tabla(resultados: list[dict]) -> str:
    claves = ["recall@1", "recall@5", "mrr", "recall@5_dificiles", "precision_umbral", "cobertura_umbral",
              "sugerencias_por_reporte", "fuga_datos_personales", "inyecciones_obedecidas",
              "json_invalido_tras_reintento", "normalizar_ms_p95", "vectorizar_ms_por_texto"]
    filas = ["| métrica | " + " | ".join(r["config"] for r in resultados) + " |",
             "| --- | " + " | ".join("---" for _ in resultados) + " |"]
    for k in claves:
        filas.append(f"| {k} | " + " | ".join("—" if r[k] is None else str(r[k]) for r in resultados) + " |")
    return "\n".join(filas)


def main() -> None:
    from ia.proveedores import ChatProvider, EmbeddingProvider

    p = argparse.ArgumentParser()
    p.add_argument("--config", nargs="+", default=["crudo", "heuristica", "llm"],
                   choices=["crudo", "heuristica", "llm"])
    p.add_argument("--datos", default=str(AQUI / "datos" / "set_matching.json"))
    p.add_argument("--limite", type=int, default=None)
    a = p.parse_args()

    datos = json.loads(Path(a.datos).read_text(encoding="utf-8"))
    emb = EmbeddingProvider.desde_entorno()
    chat = ChatProvider.desde_entorno() if "llm" in a.config else None
    resultados = []
    for c in a.config:
        print(f"Evaluando {c} ...", flush=True)
        resultados.append(evaluar(datos, c, emb.vectorizar, chat, a.limite))
    print()
    print(f"Embeddings: {emb.modelo}" + (f" · LLM: {chat.modelo}" if chat else ""))
    print(tabla(resultados))
    salida = AQUI / "resultados" / f"{datetime.now():%Y%m%d-%H%M}.json"
    salida.parent.mkdir(exist_ok=True)
    salida.write_text(json.dumps({"embeddings": emb.modelo, "llm": chat.modelo if chat else None,
                                  "resultados": resultados}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
