"""Agente analista: lee gold del lake, calcula indicadores y predicción, y deja un informe por sede.

Pasos (cada uno es una herramienta con permiso explícito y queda en la traza):
1. leer_gold            tablas agregadas del lake (sin datos personales por construcción)
2. calcular_metricas    tasa de recuperación, días típicos, zonas/franjas críticas, precisión del matching
3. predecir             próximas 4 semanas con estacionalidad académica + backtest contra la ingenua
4. redactar_resumen     el LLM escribe 4-6 frases SOLO con esos números; se verifica que no invente cifras
5. guardar_informe      fila en informe_analitica (la API la sirve en GET /analitica/resumen)

Si el LLM falla, se pasa del presupuesto o menciona un número que no está en los datos, el resumen
sale de una plantilla fija (estado "respaldo" en la traza). El LLM nunca calcula nada.

    python -m harness.analista            # una corrida ahora (todas las sedes + global)
"""

import json
import logging
import re
from datetime import UTC, date, datetime, timedelta

from psycopg import Connection
from psycopg.types.json import Jsonb

from harness.lago import LectorGold
from harness.nucleo import Agente, LimiteExcedido, Limites
from ia.pronostico import Semana, backtest, pronosticar

log = logging.getLogger("analista")

HORIZONTE = 4
DIAS = {1: "lunes", 2: "martes", 3: "miércoles", 4: "jueves", 5: "viernes", 6: "sábado", 7: "domingo"}

SISTEMA_ANALISTA = """Eres analista del servicio de objetos perdidos de una universidad. Escribes para el
administrador de una sede un resumen breve y útil en español de Colombia.

Recibes hechos YA calculados y redactados. Reglas estrictas:
- Copia las cifras tal como vienen. No hagas cuentas, no restes porcentajes, no inventes números.
- Usa exactamente las expresiones de tiempo de los datos ("esta semana", "la próxima semana", el mes).
- 4 a 6 frases, en este orden:
  1. La recuperación del mes: el porcentaje recuperado y cómo cambió frente al mes anterior.
  2. Dónde y cuándo se pierden más cosas.
  3. Qué se espera (perdidas_esperadas de la primera semana de la predicción) y si es semana de parciales.
  4. Qué tan confiable es la predicción, en una frase.
  5. Una recomendación práctica para el administrador (por ejemplo, reforzar avisos o rondas en la zona crítica).
- No menciones personas ni datos personales.

Responde SOLO con JSON: {"resumen": "..."}"""

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
TIPO_SEMANA = {"parciales": "semana de parciales", "vacaciones": "vacaciones", "inicio": "inicio de semestre",
               "normal": "semana normal"}
CUANDO = {0: "esta semana", 1: "la próxima semana", 2: "dentro de dos semanas", 3: "dentro de tres semanas"}

_NUMERO = re.compile(r"\d{1,3}(?:\.\d{3})+(?!\d)|\d+(?:[.,]\d+)?")


def _leer_numeros(texto: str) -> list[tuple[float, bool]]:
    """(valor, escrito_con_decimales) de un texto en español: 1.234 (miles), 54,2 y 1,0 (decimales)."""
    salida = []
    for m in _NUMERO.findall(texto):
        if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", m):
            salida.append((float(m.replace(".", "")), False))
        else:
            salida.append((round(float(m.replace(",", ".")), 2), "," in m or "." in m))
    return salida


def _numeros(texto: str) -> set[float]:
    return {v for v, _ in _leer_numeros(texto)}


def cifras_inventadas(resumen: str, hechos: dict) -> set[float]:
    """Números del resumen que no salen de los hechos (se permiten enteros pequeños: '3 zonas', '4 semanas')."""
    permitidas = _numeros(json.dumps(hechos, ensure_ascii=False))

    def sale_de_los_datos(n: float) -> bool:  # igual, o el mismo número redondeado a entero o a 1 decimal
        return any(abs(n - p) < 0.051 or n == round(p) or n == round(p, 1) for p in permitidas)

    # Enteros pequeños ("3 zonas", "4 semanas") se permiten; un decimal como 1,0 no: suele ser una resta del LLM
    return {n for n, decimal in _leer_numeros(resumen) if (n > 10 or decimal) and not sale_de_los_datos(n)}


def cifras_faltantes(resumen: str, obligatorias: list[float]) -> list[float]:
    """Cifras clave que el resumen debe mencionar (sin ellas, el texto es vago y no sirve)."""
    presentes = _numeros(resumen)
    return [o for o in obligatorias if not any(abs(o - p) < 0.051 or p == round(o) for p in presentes)]


def _rango_semana(inicio: str) -> str:
    d = date.fromisoformat(inicio)
    fin = d + timedelta(days=6)
    if d.month == fin.month:
        return f"{d.day} al {fin.day} de {MESES[fin.month - 1]}"
    return f"{d.day} de {MESES[d.month - 1]} al {fin.day} de {MESES[fin.month - 1]}"


def hechos_para_redactar(h: dict, hoy: date) -> tuple[dict, list[float]]:
    """Hechos en lenguaje llano para un modelo pequeño: fechas en palabras, cambios ya calculados,
    expresiones de tiempo listas. Devuelve también las cifras que el resumen debe incluir."""
    m, p = h["metricas"], h["prediccion"]
    out: dict = {"sede": h["sede"]}
    obligatorias: list[float] = []
    if mes := m.get("mes"):
        anio, mm = (int(x) for x in mes["periodo"].split("-"))
        r = {"mes": f"{MESES[mm - 1]} de {anio}", "objetos_reportados": mes["reportados"],
             "porcentaje_recuperado": mes["tasa_recuperacion_pct"]}
        obligatorias.append(mes["tasa_recuperacion_pct"])
        if mes.get("tasa_mes_anterior_pct") is not None:
            cambio = round(mes["tasa_recuperacion_pct"] - mes["tasa_mes_anterior_pct"], 1)
            r["porcentaje_recuperado_mes_anterior"] = mes["tasa_mes_anterior_pct"]
            puntos = f"{abs(cambio):.1f}".replace(".", ",")
            r["cambio_frente_al_mes_anterior"] = (f"subió {puntos} puntos" if cambio > 0 else
                                                  f"bajó {puntos} puntos" if cambio < 0 else "se mantuvo igual")
        if mes.get("dias_tipicos_hasta_recuperar") is not None:
            r["dias_tipicos_hasta_recuperar"] = mes["dias_tipicos_hasta_recuperar"]
        for clave, nombre in (("categoria_menos_recuperada", "categoria_que_menos_se_recupera"),
                              ("categoria_mas_recuperada", "categoria_que_mas_se_recupera")):
            if c := mes.get(clave):
                r[nombre] = f"{c['categoria']} ({_es(c['tasa_pct'])} %)"
        out["recuperacion"] = r
    if zc := m.get("zonas_criticas"):
        out["donde_y_cuando_se_pierde_mas"] = [
            f"{z['zona']}, los {z['dia']} de {z['franja'].replace('-', ' a ')} h ({_es(z['perdidas'])} pérdidas "
            f"en el histórico)" for z in zc]
    if semanas := p.get("semanas"):
        lunes_hoy = hoy - timedelta(days=hoy.weekday())
        pred = []
        for s in semanas[:2]:
            dist = (date.fromisoformat(s["semana_inicio"]) - lunes_hoy).days // 7
            pred.append({"cuando": CUANDO.get(dist, f"la semana del {_rango_semana(s['semana_inicio'])}"),
                         "fechas": _rango_semana(s["semana_inicio"]), "tipo_de_semana": TIPO_SEMANA[s["clase"]],
                         "perdidas_esperadas": round(s["esperado"]),
                         "rango_probable": f"entre {_es(s['minimo_90'])} y {_es(s['maximo_90'])}"})
        out["prediccion"] = pred
        obligatorias.append(pred[0]["perdidas_esperadas"])
    if bt := p.get("backtest"):
        out["confiabilidad_de_la_prediccion"] = (
            f"buena: en las últimas {bt['semanas_evaluadas']} semanas se equivocó en promedio "
            f"{_es(bt['mae_modelo'])} objetos por semana, frente a {_es(bt['mae_ingenuo'])} de una estimación simple"
            if bt["gana_modelo"] else
            "baja: no supera a una estimación simple, tómela con cautela")
    if mt := m.get("matching_4_semanas"):
        out["sugerencias_de_la_ia"] = (f"{_es(mt['precision_pct'])} % de las coincidencias revisadas en las últimas "
                                       f"4 semanas fueron correctas")
    return out, obligatorias


def _es(n: float | int | None) -> str:
    """Número en formato colombiano: 1.234 y 50,7."""
    if n is None:
        return "sin dato"
    if isinstance(n, int) or float(n).is_integer():
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")


def plantilla(h: dict) -> str:
    m, p = h["metricas"], h["prediccion"]
    partes = []
    if m.get("mes"):
        mes = m["mes"]
        partes.append(f"En {mes['periodo']} se reportaron {_es(mes['reportados'])} objetos perdidos y se "
                      f"recuperó el {_es(mes['tasa_recuperacion_pct'])} % "
                      f"(mes anterior: {_es(mes['tasa_mes_anterior_pct'])} %).")
        if mes.get("categoria_menos_recuperada"):
            c = mes["categoria_menos_recuperada"]
            partes.append(f"La categoría que menos se recupera es {c['categoria']} ({_es(c['tasa_pct'])} %).")
    if m.get("zonas_criticas"):
        z = m["zonas_criticas"][0]
        partes.append(f"El punto más crítico es {z['zona']} los {z['dia']} en la franja {z['franja']} "
                      f"({_es(z['perdidas'])} pérdidas en el histórico).")
    if p.get("semanas"):
        s = p["semanas"][0]
        extra = (" Es semana de parciales: conviene reforzar los avisos en esa zona."
                 if s["clase"] == "parciales" else "")
        partes.append(f"Para la semana del {s['semana_inicio']} se esperan unas {_es(round(s['esperado']))} pérdidas "
                      f"(entre {_es(s['minimo_90'])} y {_es(s['maximo_90'])}).{extra}")
    if p.get("backtest") and not p["backtest"]["gana_modelo"]:
        partes.append("La predicción no supera a una estimación simple: tómela con cautela.")
    return " ".join(partes) or "Aún no hay datos suficientes en el lake para un informe."


class Analista(Agente):
    nombre = "analista"
    limites = Limites(max_llamadas_llm=2, max_tokens=6000, max_segundos=180)
    herramientas_permitidas = frozenset({"leer_gold", "calcular_metricas", "predecir", "redactar_resumen",
                                         "guardar_informe"})

    def __init__(self, trazas, conn: Connection, lector: LectorGold, chat=None, hoy: date | None = None):
        super().__init__(trazas)
        self.conn, self.lector, self.chat = conn, lector, chat
        self.hoy = hoy or datetime.now(UTC).date()
        self._gold: dict[str, list[dict]] | None = None

    # ------------------------------------------------------------------ corrida completa
    def correr(self) -> list[dict]:
        """Un informe global y uno por sede con datos. Devuelve las trazas."""
        self._gold = None
        serie = self._leer()["serie_semanal"]
        if not serie:
            log.info("analista: gold vacío, no hay informe que escribir")
            return []
        sedes = sorted({f["sede_id"] for f in serie})
        trazas = []
        for sede in [None, *sedes]:
            trazas.append(self.ejecutar({"tipo_evento": "analitica.programada", "agregado_id": sede or "global",
                                         "id": 0, "sede_id": sede}))
        return trazas

    def _leer(self) -> dict[str, list[dict]]:
        if self._gold is None:
            self._gold = {n: self.lector.tabla(n) for n in ("serie_semanal", "kpi_recuperacion_mensual",
                                                            "mapa_calor_zona_hora", "calidad_matching",
                                                            "calendario")}
        return self._gold

    def manejar(self, evento: dict) -> dict:
        sede = evento["sede_id"]
        gold = self.usar("leer_gold", self._leer, entrada="5 tablas gold")
        metricas = self.usar("calcular_metricas", self._metricas, gold, sede, entrada={"sede": sede})
        prediccion = self.usar("predecir", self._predecir, gold, sede, entrada={"sede": sede})
        hechos = {"sede": metricas.pop("sede_nombre"), "metricas": metricas, "prediccion": prediccion}
        resumen, fuente = self._resumir(hechos)
        informe_id = self.usar("guardar_informe", self._guardar, sede, hechos, resumen, fuente,
                               entrada={"sede": sede, "fuente": fuente})
        return {"informe": informe_id, "fuente": fuente}

    # ------------------------------------------------------------------ herramientas
    def _semanas_completas(self, gold: dict, sede: int | None) -> tuple[list[Semana], list[float]]:
        lunes_actual = self.hoy - timedelta(days=self.hoy.weekday())
        por_semana: dict[date, float] = {}
        for f in gold["serie_semanal"]:
            if (sede is None or f["sede_id"] == sede) and f["semana_inicio"] < lunes_actual:
                por_semana[f["semana_inicio"]] = por_semana.get(f["semana_inicio"], 0) + f["perdidas"]
        if not por_semana:
            return [], []
        cal = {c["semana_inicio"]: c for c in gold["calendario"]}
        semanas, y = [], []
        s = min(por_semana)
        while s < lunes_actual:  # semanas sin pérdidas cuentan como 0
            c = cal.get(s, {})
            semanas.append(Semana(s, c.get("semana_semestre"), bool(c.get("es_parciales"))))
            y.append(por_semana.get(s, 0.0))
            s += timedelta(days=7)
        return semanas, y

    def _predecir(self, gold: dict, sede: int | None) -> dict:
        semanas, y = self._semanas_completas(gold, sede)
        if len(semanas) < 4:
            return {"semanas": [], "backtest": None, "nota": "menos de 4 semanas de historia"}
        cal = {c["semana_inicio"]: c for c in gold["calendario"]}
        futuras = []
        for i in range(1, HORIZONTE + 1):
            s = semanas[-1].inicio + timedelta(days=7 * i)
            c = cal.get(s, {})
            futuras.append(Semana(s, c.get("semana_semestre"), bool(c.get("es_parciales"))))
        return {"semanas": pronosticar(semanas, y, futuras), "backtest": backtest(semanas, y),
                "ultima_semana_real": {"semana_inicio": semanas[-1].inicio.isoformat(), "perdidas": int(y[-1])}}

    def _metricas(self, gold: dict, sede: int | None) -> dict:
        kpi = [f for f in gold["kpi_recuperacion_mensual"] if sede is None or f["sede_id"] == sede]
        nombre = next((f["sede"] for f in kpi), None) if sede is not None else "Todas las sedes"
        salida: dict = {"sede_nombre": nombre or f"Sede {sede}"}

        # Último mes completo y el anterior
        mes_actual = (self.hoy.year, self.hoy.month)
        meses = sorted({(f["anio"], f["mes"]) for f in kpi if (f["anio"], f["mes"]) < mes_actual})
        if meses:
            def total(am):
                filas = [f for f in kpi if (f["anio"], f["mes"]) == am]
                rep, rec = sum(f["reportados"] for f in filas), sum(f["recuperados"] for f in filas)
                dias = [(f["mediana_dias"], f["recuperados"]) for f in filas if f["mediana_dias"] is not None]
                pond = sum(d * n for d, n in dias) / max(1, sum(n for _, n in dias)) if dias else None
                return filas, rep, rec, pond

            filas, rep, rec, dias = total(meses[-1])
            _, rep_a, rec_a, _ = total(meses[-2]) if len(meses) > 1 else (None, 0, 0, None)
            por_cat: dict[str, list[int]] = {}
            for f in filas:
                acc = por_cat.setdefault(f["categoria"], [0, 0])
                acc[0] += f["reportados"]
                acc[1] += f["recuperados"]
            cats = sorted(((c, round(100 * r / n, 1), n) for c, (n, r) in por_cat.items() if n >= 10),
                          key=lambda x: x[1])
            salida["mes"] = {
                "periodo": f"{meses[-1][0]}-{meses[-1][1]:02d}", "reportados": rep, "recuperados": rec,
                "tasa_recuperacion_pct": round(100 * rec / rep, 1) if rep else 0.0,
                "tasa_mes_anterior_pct": round(100 * rec_a / rep_a, 1) if rep_a else None,
                "dias_tipicos_hasta_recuperar": round(dias, 1) if dias is not None else None,
                "categoria_menos_recuperada": {"categoria": cats[0][0], "tasa_pct": cats[0][1]} if cats else None,
                "categoria_mas_recuperada": {"categoria": cats[-1][0], "tasa_pct": cats[-1][1]} if cats else None,
            }

        # Zonas, días y franjas con más pérdidas (histórico)
        celdas: dict[tuple, int] = {}
        for f in gold["mapa_calor_zona_hora"]:
            if (sede is None or f["sede_id"] == sede) and f["franja"] != "sin hora":
                k = (f["zona"], f["dia_semana"], f["franja"])
                celdas[k] = celdas.get(k, 0) + f["perdidas"]
        salida["zonas_criticas"] = [{"zona": z, "dia": DIAS.get(d, str(d)), "franja": fr, "perdidas": n}
                                    for (z, d, fr), n in sorted(celdas.items(), key=lambda x: -x[1])[:3]]

        # Precisión del matching (todas las sedes: la tabla gold no se separa por sede)
        cm = sorted(gold["calidad_matching"], key=lambda f: f["semana_inicio"])[-4:]
        decididas = sum(f["aceptadas"] + f["rechazadas"] for f in cm)
        if decididas:
            salida["matching_4_semanas"] = {"sugeridas": sum(f["sugeridas"] for f in cm),
                                            "precision_pct": round(100 * sum(f["aceptadas"] for f in cm)
                                                                   / decididas, 1)}
        return salida

    def _resumir(self, hechos: dict) -> tuple[str, str]:
        if self.chat is None:
            return plantilla(hechos), "plantilla"
        redaccion, obligatorias = hechos_para_redactar(hechos, self.hoy)
        datos = json.dumps(redaccion, ensure_ascii=False, default=str)
        for intento in range(2):
            try:
                texto = self.usar("redactar_resumen", self._llm, datos, entrada=f"intento {intento + 1}")
                resumen = str(json.loads(texto).get("resumen", "")).strip()
                malas = cifras_inventadas(resumen, redaccion)
                faltan = cifras_faltantes(resumen, obligatorias)
                if resumen and not malas and not faltan:
                    return resumen, "llm"
                motivo = (f"cifras no presentes en los datos: {sorted(malas)}" if malas
                          else f"faltan cifras clave: {faltan}" if faltan else "resumen vacío")
                self.ejecucion.pasos.append({"herramienta": "verificar_cifras", "ok": False, "ms": 0,
                                             "entrada_resumen": "resumen del LLM", "salida_resumen": motivo,
                                             "rechazado": resumen[:600]})  # sin datos personales: solo agregados
            except LimiteExcedido:
                break  # sin presupuesto: plantilla
            except Exception as exc:  # noqa: BLE001 - cualquier fallo del LLM cae a la plantilla
                log.warning("analista: el LLM falló (%s)", type(exc).__name__)
        self.ejecucion.respaldo = True
        return plantilla(hechos), "plantilla"

    def _llm(self, datos: str) -> str:
        texto, uso = self.chat.completar([{"role": "system", "content": SISTEMA_ANALISTA},
                                          {"role": "user", "content": datos}], json=True, max_tokens=500)
        self.ejecucion.proveedor, self.ejecucion.modelo = "openai-compatible", self.chat.modelo
        self.ejecucion.registrar_llm(uso)
        return texto

    def _guardar(self, sede: int | None, hechos: dict, resumen: str, fuente: str) -> str:
        ult = hechos["prediccion"].get("ultima_semana_real", {}).get("semana_inicio")
        datos_hasta = (date.fromisoformat(ult) + timedelta(days=6)) if ult else self.hoy
        fila = self.conn.execute(
            "INSERT INTO informe_analitica (sede_id, datos_hasta, metricas, prediccion, resumen, resumen_fuente, "
            "modelo_llm, ejecucion_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (sede, datos_hasta, Jsonb({"sede": hechos["sede"], **hechos["metricas"]}), Jsonb(hechos["prediccion"]),
             resumen, fuente, self.chat.modelo if fuente == "llm" else None, self.ejecucion.ejecucion_id),
        ).fetchone()
        return str(fila["id"])


def main() -> None:
    import psycopg
    from psycopg.rows import dict_row

    from harness.config import Config
    from harness.worker import construir_trazas
    from ia.proveedores import ChatProvider

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    cfg = Config()
    lector = LectorGold.desde_entorno()
    if lector is None:
        raise SystemExit("No hay lake configurado (S3_ENDPOINT o LAGO_LOCAL)")
    conn = psycopg.connect(cfg.database_url, autocommit=True, row_factory=dict_row)
    chat = ChatProvider.desde_entorno() if cfg.analista_llm else None
    for t in Analista(construir_trazas(cfg), conn, lector, chat).correr():
        log.info("analista %s %s %s", t["disparador"]["ref"], t["estado"], t.get("salida"))


if __name__ == "__main__":
    main()
