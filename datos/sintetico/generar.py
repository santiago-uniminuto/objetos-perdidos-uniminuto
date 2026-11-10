"""Genera ≥ 1 millón de reportes sintéticos en varias sedes, con COPY (rápido) y reproducible.

Patrones que imita (para que la analítica y la predicción tengan algo que encontrar):
- más pérdidas entre semana, casi nada en vacaciones y picos en semanas de parciales (8 y 16);
- horas pico a media mañana y en la tarde; zonas y categorías con pesos distintos;
- sedes de tamaño desigual (ley de Zipf): sirve para medir el balance de Citus (ADR-012);
- tasa de recuperación distinta por categoría y días hasta la entrega con cola larga.

También escribe los eventos del outbox, así el ETL lleva todo al lake por el camino real.
Los agentes (matcher, notificador) NO procesan lo sintético: sus offsets saltan al final.

    python -m sintetico.generar --reportes 100000            # prueba (~1 min)
    python -m sintetico.generar --reportes 1000000 --sedes 12 # escala (~10-15 min, ~4 GB)

Todo es inventado: nombres de una lista fija, documentos con prefijo SIN.
"""

import argparse
import json
import os
import random
import time
import uuid
from datetime import UTC, date, datetime, timedelta

import numpy as np
import psycopg

from lago.calendario import PARCIALES, semana_semestre

ZONAS = {"Aulas": 20, "Biblioteca": 16, "Cafeterías": 16, "Baños": 10, "CRAI - zona de descanso": 8,
         "Parqueadero": 6, "Auditorios": 6, "Zonas verdes": 6, "Terrazas": 5, "Admisiones": 4,
         "Sala de profesores": 3}
# id: (peso, tasa de recuperación, tipos)
CATEGORIAS = {
    7: (24, 0.48, ["Termo", "Botella", "Vaso"]),
    1: (18, 0.62, ["Celular", "Audífonos", "Cargador", "Calculadora"]),
    4: (16, 0.50, ["Billetera", "Gafas", "Maleta", "Sombrilla"]),
    3: (14, 0.38, ["Chaqueta", "Buzo", "Gorra"]),
    5: (10, 0.35, ["Cuaderno", "Libro", "Cartuchera"]),
    2: (10, 0.72, ["Carné", "Cédula", "Tarjeta"]),
    6: (5, 0.55, ["Llavero"]),
    8: (3, 0.30, ["Objeto"]),
}
COLORES = ["azul", "negro", "blanco", "rojo", "verde", "gris", "rosado", "morado", "café", "amarillo"]
NOMBRES = ["Ana", "Carlos", "Laura", "Andrés", "Valentina", "Juan", "Daniela", "Santiago", "Camila", "Felipe",
           "Paula", "Sebastián", "María", "David", "Natalia", "Mateo", "Sofía", "Julián", "Isabella", "Diego"]
APELLIDOS = ["Gómez", "Rodríguez", "Martínez", "Pérez", "López", "García", "Hernández", "Díaz", "Torres",
             "Ramírez", "Castro", "Vargas", "Rojas", "Moreno", "Ortiz", "Suárez", "Jiménez", "Cruz"]
HORAS = np.array([7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21])
PESO_HORAS = np.array([3, 6, 9, 12, 11, 8, 7, 10, 11, 10, 8, 6, 4, 3, 2], dtype=float)


def _uuid(rnd: random.Random) -> str:
    return str(uuid.UUID(int=rnd.getrandbits(128), version=4))


def pesos_dias(desde: date, hasta: date) -> tuple[list[date], np.ndarray]:
    dias, pesos = [], []
    d = desde
    while d <= hasta:
        semana = semana_semestre(d)
        w = (1.0, 1.0, 1.0, 1.0, 0.9, 0.35, 0.05)[d.weekday()]
        w *= 0.15 if semana is None else (1.8 if semana in PARCIALES else 1.2 if semana == 1 else 1.0)
        dias.append(d)
        pesos.append(w)
        d += timedelta(days=1)
    p = np.array(pesos)
    return dias, p / p.sum()


def preparar_sedes(conn, n_sedes: int, rnd: random.Random) -> dict:
    """Crea las sedes, zonas y un admin sintético por sede. Devuelve {sede: {admin, zonas}}."""
    from argon2 import PasswordHasher

    hash_inutilizable = PasswordHasher().hash(_uuid(rnd))  # nadie conoce esta clave
    sedes = {}
    for s in range(1, n_sedes + 1):
        conn.execute("INSERT INTO sede (id, codigo, nombre, ciudad) VALUES (%s, %s, %s, 'Sintética') "
                     "ON CONFLICT (id) DO NOTHING", (s, f"SEDE-{s:02d}", f"Sede sintética {s:02d}"))
        for z in ZONAS:
            conn.execute("INSERT INTO zona (sede_id, nombre) VALUES (%s, %s) ON CONFLICT DO NOTHING", (s, z))
        email = f"admin.sintetico.{s:02d}@sintetico.uniminuto.edu.co"
        conn.execute("INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) VALUES "
                     "(%s, %s, %s, %s, 'admin_sede') ON CONFLICT DO NOTHING",
                     (s, email, f"Admin sintético {s:02d}", hash_inutilizable))
        admin = conn.execute("SELECT id FROM usuario WHERE lower(email) = %s", (email,)).fetchone()[0]
        zonas = dict(conn.execute("SELECT nombre, id FROM zona WHERE sede_id = %s", (s,)).fetchall())
        sedes[s] = {"admin": str(admin), "zonas": zonas}
    return sedes


COPY_HALLAZGO = ("COPY hallazgo (id, sede_id, creado_en, categoria_id, zona_id, descripcion, descripcion_publica, "
                 "fecha_hallazgo, hora_aprox, estado, vence_en, registrado_por, cerrado_en) FROM STDIN")
COPY_REPORTE = ("COPY reporte_perdida (id, sede_id, creado_en, estudiante_id, categoria_id, zona_id, descripcion, "
                "descripcion_publica, fecha_perdida, hora_aprox, estado, registrado_por, cerrado_en) FROM STDIN")
COPY_COINCIDENCIA = ("COPY coincidencia (id, sede_id, creado_en, reporte_id, reporte_creado_en, hallazgo_id, "
                     "hallazgo_creado_en, similitud, puntaje, estado, decidido_por, decidido_en, motivo_rechazo, "
                     "modelo_embedding) "
                     "FROM STDIN")
COPY_ENTREGA = ("COPY entrega (id, sede_id, creado_en, coincidencia_id, estudiante_id, numero_acta, registrado_por, "
                "verificacion_ok) FROM STDIN")
COPY_OUTBOX = "COPY outbox (agregado, agregado_id, sede_id, tipo_evento, payload, creado_en) FROM STDIN"
LOTE = 50_000


def _copiar(cur, sql: str, filas: list[tuple]) -> None:
    if filas:
        with cur.copy(sql) as cp:
            for f in filas:
                cp.write_row(f)


class Generador:
    """Genera por lotes para que 1 millón de reportes quepa en poca memoria."""

    def __init__(self, conn, n_sedes: int, desde: date, hasta: date, semilla: int):
        self.conn, self.hasta, self.semilla = conn, hasta, semilla
        self.rnd, self.rng = random.Random(semilla), np.random.default_rng(semilla)
        self.ahora = datetime.now(UTC)
        self.sedes = preparar_sedes(conn, n_sedes, self.rnd)
        self.dias, self.p_dias = pesos_dias(desde, hasta)
        w = 1 / np.arange(1, n_sedes + 1) ** 1.1
        self.p_sede, self.ids_sede = w / w.sum(), np.arange(1, n_sedes + 1)
        self.nombres_zona = list(ZONAS)
        pz = np.array(list(ZONAS.values()), dtype=float)
        self.p_zona = pz / pz.sum()
        self.cats = list(CATEGORIAS)
        pc = np.array([CATEGORIAS[c][0] for c in self.cats], dtype=float)
        self.p_cat = pc / pc.sum()
        self.sin_dueno: dict[int, list[tuple]] = {s: [] for s in self.sedes}
        self.cont = {k: 0 for k in ("estudiantes", "reportes", "hallazgos", "coincidencias", "entregas", "eventos")}

    def momento(self, d: date, h: int, m: int, mas_horas: int = 0) -> datetime:
        t = datetime(d.year, d.month, d.day, int(h), int(m), tzinfo=UTC) + timedelta(hours=int(mas_horas))
        return min(t, self.ahora)

    def muestra(self, n: int) -> dict:
        r = self.rng
        return {"dia": r.choice(len(self.dias), size=n, p=self.p_dias),
                "sede": r.choice(self.ids_sede, size=n, p=self.p_sede),
                "zona": r.choice(len(self.nombres_zona), size=n, p=self.p_zona),
                "cat": r.choice(self.cats, size=n, p=self.p_cat)}

    def texto(self, cat: int) -> str:
        return f"{self.rnd.choice(CATEGORIAS[cat][2])} {self.rnd.choice(COLORES)}"

    # ------------------------------------------------------------------ etapas
    def estudiantes(self, n: int) -> list[str]:
        ids = [_uuid(self.rnd) for _ in range(n)]
        admin = self.sedes[1]["admin"]
        with self.conn.cursor() as cur:
            for i in range(0, n, LOTE):
                parte = ids[i:i + LOTE]
                _copiar(cur, "COPY estudiante (id, tipo_documento, numero_documento, nombres, apellidos, "
                        "correo_institucional) FROM STDIN",
                        [(eid, "CC", f"SIN{self.semilla:02d}{i + k:09d}", self.rnd.choice(NOMBRES),
                          self.rnd.choice(APELLIDOS), f"sin{self.semilla}.{i + k}@sintetico.uniminuto.edu.co")
                         for k, eid in enumerate(parte)])
                _copiar(cur, "COPY consentimiento (estudiante_id, version_aviso, finalidades, registrado_por) "
                        "FROM STDIN", [(eid, "sintetico", ["gestion_objeto", "notificacion_correo"], admin)
                                       for eid in parte])
        self.cont["estudiantes"] = n
        return ids

    def hallazgos_sin_dueno(self, n: int) -> None:
        with self.conn.cursor() as cur:
            for i in range(0, n, LOTE):
                m = self.muestra(min(LOTE, n - i))
                filas, eventos = [], []
                for j in range(len(m["dia"])):
                    sede, d, cat = int(m["sede"][j]), self.dias[m["dia"][j]], int(m["cat"][j])
                    zona = self.sedes[sede]["zonas"][self.nombres_zona[m["zona"][j]]]
                    creado = self.momento(d, 8 + self.rnd.randint(0, 10), self.rnd.randint(0, 59))
                    hid, texto = _uuid(self.rnd), self.texto(cat)
                    estado = "donado" if (self.hasta - d).days > 90 else "publicado"
                    filas.append((hid, sede, creado, cat, zona, f"{texto} (sintético)", texto, d, None, estado,
                                  d + timedelta(days=90), self.sedes[sede]["admin"], None))
                    self.sin_dueno[sede].append((hid, creado))
                    eventos.append(_evento("hallazgo", hid, sede, "hallazgo.creado", {
                        "id": hid, "categoria_id": cat, "zona_id": zona, "fecha": d.isoformat(), "hora": None,
                        "creado_en": creado.isoformat()}, creado))
                _copiar(cur, COPY_HALLAZGO, filas)
                _copiar(cur, COPY_OUTBOX, eventos)
                self.cont["hallazgos"] += len(filas)
                self.cont["eventos"] += len(eventos)
            self.conn.commit()

    def reportes(self, n: int, est_ids: list[str]) -> None:
        with self.conn.cursor() as cur:
            for i in range(0, n, LOTE):
                self._lote_reportes(cur, min(LOTE, n - i), i, est_ids)
                self.conn.commit()

    def _sin_dueno_cercano(self, sede: int, cuando: datetime) -> tuple | None:
        """Un hallazgo sin dueño de fechas parecidas (±14 días), como lo propondría el matcher."""
        pool = self.sin_dueno[sede]
        for _ in range(8):
            if not pool:
                return None
            hid, creado = self.rnd.choice(pool)
            if abs((creado - cuando).days) <= 14:
                return hid, creado
        return None

    def _lote_reportes(self, cur, n: int, base: int, est_ids: list[str]) -> None:
        rnd, rng = self.rnd, self.rng
        m = self.muestra(n)
        hora = rng.choice(HORAS, size=n, p=PESO_HORAS / PESO_HORAS.sum())
        minuto = rng.integers(0, 60, size=n)
        recupera = rng.random(n) < np.array([CATEGORIAS[c][1] for c in m["cat"]])
        dias_rec = np.minimum(rng.exponential(5.0, size=n).astype(int), 60)
        retraso = rng.integers(0, 30, size=n)
        est = rng.integers(0, len(est_ids), size=n)
        fr, fh, fc, fe, ev = [], [], [], [], []
        for i in range(n):
            sede, d, cat = int(m["sede"][i]), self.dias[m["dia"][i]], int(m["cat"][i])
            zona = self.sedes[sede]["zonas"][self.nombres_zona[m["zona"][i]]]
            texto, admin = self.texto(cat), self.sedes[sede]["admin"]
            hora_txt = f"{int(hora[i]):02d}:{int(minuto[i]):02d}"
            creado = self.momento(d, hora[i], minuto[i], retraso[i])
            rid, cerrado_en = _uuid(rnd), None
            if recupera[i]:
                estado = "cerrado"
                dr = int(dias_rec[i])
                fecha_h = min(d + timedelta(days=rnd.randint(0, min(dr, 3))), self.hasta)
                h_creado = self.momento(fecha_h, 8 + rnd.randint(0, 10), rnd.randint(0, 59))
                entregado = max(self.momento(d + timedelta(days=dr), 9 + rnd.randint(0, 9), rnd.randint(0, 59)),
                                creado, h_creado)
                hid, cid, eid = _uuid(rnd), _uuid(rnd), _uuid(rnd)
                sugerida = max(creado, h_creado)
                puntaje = round(0.62 + rnd.random() * 0.35, 3)
                fh.append((hid, sede, h_creado, cat, zona, f"{texto} (sintético)", texto, fecha_h, None, "cerrado",
                           fecha_h + timedelta(days=90), admin, entregado))
                fc.append((cid, sede, sugerida, rid, creado, hid, h_creado, round(0.80 + rnd.random() * 0.19, 3),
                           puntaje, "entregada", admin, sugerida, None, "sintetico"))
                fe.append((eid, sede, entregado, cid, est_ids[est[i]], f"SIN-{base + i}", admin, True))
                par = {"id": cid, "reporte_id": rid, "hallazgo_id": hid, "puntaje": puntaje}
                ev += [
                    _evento("hallazgo", hid, sede, "hallazgo.creado", {
                        "id": hid, "categoria_id": cat, "zona_id": zona, "fecha": fecha_h.isoformat(), "hora": None,
                        "creado_en": h_creado.isoformat()}, h_creado),
                    _evento("coincidencia", cid, sede, "coincidencia.sugerida", par, sugerida),
                    _evento("coincidencia", cid, sede, "coincidencia.verificada", par, sugerida + timedelta(hours=2)),
                    _evento("entrega", eid, sede, "entrega.registrada", {
                        "id": eid, "coincidencia_id": cid, "reporte_id": rid, "hallazgo_id": hid,
                        "creado_en": entregado.isoformat()}, entregado),
                ]
                cerrado_en = entregado
                # 1 de cada 5 casos recuperados tuvo antes una sugerencia equivocada que el admin rechazó
                cercano = self._sin_dueno_cercano(sede, creado) if rnd.random() < 0.2 else None
                if cercano:
                    hid2, h2 = cercano
                    cid2, cuando = _uuid(rnd), max(creado, h2)
                    p2 = round(0.60 + rnd.random() * 0.2, 3)
                    fc.append((cid2, sede, cuando, rid, creado, hid2, h2, round(0.7 + rnd.random() * 0.2, 3), p2,
                               "rechazada", admin, cuando, "Sintético: no coincide", "sintetico"))
                    ev += [_evento("coincidencia", cid2, sede, "coincidencia.sugerida",
                                   {"id": cid2, "reporte_id": rid, "hallazgo_id": hid2, "puntaje": p2}, cuando),
                           _evento("coincidencia", cid2, sede, "coincidencia.rechazada",
                                   {"id": cid2, "puntaje": p2}, cuando + timedelta(hours=1))]
            else:
                estado = "expirado" if (self.hasta - d).days > 90 else "publicado"
            fr.append((rid, sede, creado, est_ids[est[i]], cat, zona, f"{texto} (sintético)", texto, d, hora_txt,
                       estado, admin, cerrado_en))
            ev.append(_evento("reporte_perdida", rid, sede, "reporte.creado", {
                "id": rid, "categoria_id": cat, "zona_id": zona, "fecha": d.isoformat(), "hora": hora_txt,
                "creado_en": creado.isoformat()}, creado))
        # Orden de llaves foráneas: hallazgos y reportes antes que coincidencias y entregas
        for sql, filas in ((COPY_HALLAZGO, fh), (COPY_REPORTE, fr), (COPY_COINCIDENCIA, fc), (COPY_ENTREGA, fe),
                           (COPY_OUTBOX, sorted(ev, key=lambda e: e[5]))):
            _copiar(cur, sql, filas)
        for k, v in (("reportes", fr), ("hallazgos", fh), ("coincidencias", fc), ("entregas", fe), ("eventos", ev)):
            self.cont[k] += len(v)


def _evento(agregado, agregado_id, sede, tipo, payload, cuando) -> tuple:
    return (agregado, agregado_id, sede, tipo, json.dumps(payload, ensure_ascii=False), cuando)


SQL_LIMPIAR = [
    # Eventos primero: se identifican por el id del agregado sintético
    """DELETE FROM outbox o USING (
           SELECT id FROM reporte_perdida WHERE descripcion LIKE '%(sintético)'
           UNION ALL SELECT id FROM hallazgo WHERE descripcion LIKE '%(sintético)'
           UNION ALL SELECT id FROM coincidencia WHERE modelo_embedding = 'sintetico'
           UNION ALL SELECT id FROM entrega WHERE numero_acta LIKE 'SIN-%') s
       WHERE o.agregado_id = s.id""",
    "DELETE FROM entrega WHERE numero_acta LIKE 'SIN-%'",
    "DELETE FROM coincidencia WHERE modelo_embedding = 'sintetico'",
    "DELETE FROM reporte_perdida WHERE descripcion LIKE '%(sintético)'",
    "DELETE FROM hallazgo WHERE descripcion LIKE '%(sintético)'",
    "DELETE FROM consentimiento WHERE version_aviso = 'sintetico'",
    "DELETE FROM estudiante WHERE numero_documento LIKE 'SIN%'",
]


def limpiar(conn) -> dict:
    """Borra todo lo sintético (sedes y admins se quedan: no estorban). El lake se borra aparte."""
    borrados = {}
    for sql in SQL_LIMPIAR:
        borrados[sql.split()[2]] = conn.execute(sql).rowcount
    conn.commit()
    return borrados


def generar(conn, n_reportes: int, n_sedes: int, desde: date, hasta: date, semilla: int) -> dict:
    t0 = time.perf_counter()
    g = Generador(conn, n_sedes, desde, hasta, semilla)
    est_ids = g.estudiantes(max(1, int(n_reportes * 0.8)))
    conn.commit()
    g.hallazgos_sin_dueno(int(n_reportes * 0.45))
    g.reportes(n_reportes, est_ids)
    # Los agentes no procesan lo sintético (serían millones de llamadas al LLM); el ETL sí.
    conn.execute("UPDATE consumidor_outbox SET ultimo_id = (SELECT max(id) FROM outbox) "
                 "WHERE consumidor IN ('matcher', 'notificador')")
    conn.commit()
    cont = dict(g.cont)
    cont["filas_totales"] = sum(cont.values()) + cont["estudiantes"]  # + consentimientos
    cont["segundos"] = round(time.perf_counter() - t0, 1)
    return cont


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reportes", type=int, default=100_000)
    p.add_argument("--sedes", type=int, default=12)
    p.add_argument("--desde", type=date.fromisoformat, default=date(2024, 11, 1))
    p.add_argument("--hasta", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    p.add_argument("--semilla", type=int, default=7)
    p.add_argument("--limpiar", action="store_true", help="borra lo sintético anterior antes de generar")
    p.add_argument("--solo-limpiar", action="store_true")
    a = p.parse_args()
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        if a.limpiar or a.solo_limpiar:
            print("borrado:", limpiar(conn))
            if a.solo_limpiar:
                return
        hay = conn.execute("SELECT 1 FROM estudiante WHERE numero_documento LIKE %s LIMIT 1",
                           (f"SIN{a.semilla:02d}%",)).fetchone()
        if hay:
            raise SystemExit(f"Ya hay datos sintéticos con semilla {a.semilla}: use --limpiar u otra --semilla")
        resumen = generar(conn, a.reportes, a.sedes, a.desde, a.hasta, a.semilla)
    for k, v in resumen.items():
        print(f"{k:>16}: {v:,}" if isinstance(v, int) else f"{k:>16}: {v}")


if __name__ == "__main__":
    main()
