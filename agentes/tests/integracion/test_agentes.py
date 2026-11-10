"""Agentes de punta a punta contra PostgreSQL real (con las migraciones del backend aplicadas).

LLM y embeddings simulados (sin Ollama), Redis con fakeredis y Mongo con mongomock.
    PRUEBAS_INTEGRACION=1 DATABASE_URL=postgresql://... pytest tests/integracion
"""

import hashlib
import json
import math
import os
import re
import uuid
from datetime import date

import fakeredis
import mongomock
import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from harness.matcher import Matcher
from harness.notificador import Notificador
from harness.nucleo import RegistroTrazas
from harness.worker import procesar_lote
from ia.normalizador import heuristica
from ia.proveedores import Uso

pytestmark = pytest.mark.skipif(
    os.environ.get("PRUEBAS_INTEGRACION") != "1", reason="requiere PostgreSQL (PRUEBAS_INTEGRACION=1)"
)
URL = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:5432/objetos_perdidos")


class EmbeddingsFalsos:
    """Bolsa de trigramas en 1024 dimensiones (la columna es vector(1024))."""

    modelo = "prueba-1024"

    def vectorizar(self, textos):
        salida = []
        for t in textos:
            v = [0.0] * 1024
            plano = re.sub(r"\s+", " ", t.lower())
            for i in range(len(plano) - 2):
                v[int(hashlib.md5(plano[i:i + 3].encode(), usedforsecurity=False).hexdigest(), 16) % 1024] += 1
            n = math.sqrt(sum(x * x for x in v)) or 1
            salida.append([x / n for x in v])
        return salida


class ChatFalso:
    """Normaliza con la heurística y explica con un JSON fijo; registra lo que recibe."""

    modelo = "qwen-falso"

    def __init__(self):
        self.mensajes_recibidos = []

    def completar(self, mensajes, **_):
        self.mensajes_recibidos.append(mensajes[-1]["content"])
        ultimo = mensajes[-1]["content"]
        if "<descripcion>" in ultimo:
            texto = ultimo.split("<descripcion>\n")[1].split("\n</descripcion>")[0]
            categoria = ultimo.split(": ")[1].split("\n")[0]
            return heuristica(texto, categoria).model_dump_json(), Uso(50, 30, 5.0)
        return json.dumps({"coincide_en": ["color", "tipo"], "difiere_en": [], "confianza": "alta",
                           "explicacion": "Ambos son termos azules con sticker."}), Uso(80, 40, 5.0)


class CorreoFalso:
    def __init__(self):
        self.enviados = []

    def enviar(self, destino, asunto, cuerpo):
        self.enviados.append({"destino": destino, "asunto": asunto, "cuerpo": cuerpo})
        return "enviado"


def _retirar_restos(conn) -> None:
    """Saca de circulación lo que dejaron corridas anteriores (mismos textos = mismos vectores).

    Sin esto, con muchas corridas en la misma base, las copias viejas llenan los MAX_CANDIDATOS
    del matcher y la bandeja de la API (que pagina por puntaje).
    """
    conn.execute("UPDATE coincidencia co SET estado = 'rechazada', motivo_rechazo = 'resto de pruebas', "
                 "decidido_en = now(), decidido_por = h.registrado_por FROM hallazgo h "
                 "WHERE h.id = co.hallazgo_id AND h.sede_id = co.sede_id AND co.modelo_embedding = 'prueba-1024' "
                 "AND co.estado IN ('sugerida', 'verificada')")
    conn.execute("UPDATE hallazgo SET estado = 'donado' WHERE estado IN ('publicado', 'en_coincidencia') AND id IN "
                 "(SELECT objeto_id FROM objeto_embedding WHERE modelo = 'prueba-1024')")
    conn.execute("UPDATE reporte_perdida SET estado = 'expirado' WHERE estado IN ('publicado', 'en_coincidencia') "
                 "AND id IN (SELECT objeto_id FROM objeto_embedding WHERE modelo = 'prueba-1024')")


@pytest.fixture
def entorno():
    conn = psycopg.connect(URL, autocommit=True, row_factory=dict_row)
    _retirar_restos(conn)
    # Los consumidores arrancan después de cualquier evento previo de otras pruebas
    conn.execute("UPDATE consumidor_outbox SET ultimo_id = (SELECT coalesce(max(id), 0) FROM outbox) "
                 "WHERE consumidor IN ('matcher', 'notificador')")
    r = fakeredis.FakeRedis(decode_responses=True)
    trazas = mongomock.MongoClient()["objetos_perdidos"]["trazas_agente"]
    chat, correo = ChatFalso(), CorreoFalso()
    registro = RegistroTrazas(trazas)
    matcher = Matcher(registro, conn, chat, EmbeddingsFalsos(), "llm", True)
    notificador = Notificador(registro, conn, r, correo)
    yield {"conn": conn, "r": r, "trazas": trazas, "chat": chat, "correo": correo,
           "matcher": matcher, "notificador": notificador}
    _retirar_restos(conn)
    conn.close()


def _base(conn) -> dict:
    sufijo = uuid.uuid4().hex[:8]
    admin = conn.execute("INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) VALUES "
                         "(1, %s, 'Admin', 'x', 'admin_sede') RETURNING id", (f"ag-{sufijo}@pruebas.edu.co",)
                         ).fetchone()["id"]
    est = conn.execute("INSERT INTO estudiante (tipo_documento, numero_documento, nombres, apellidos, "
                       "correo_institucional) VALUES ('CC', %s, 'Valentina', 'López', 'vale@pruebas.edu.co') "
                       "RETURNING id", (str(uuid.uuid4().int)[:10],)).fetchone()["id"]
    conn.execute("INSERT INTO consentimiento (estudiante_id, version_aviso, finalidades, registrado_por) "
                 "VALUES (%s, 'v1', '{gestion_objeto,notificacion_correo}', %s)", (est, admin))
    zona = conn.execute("SELECT id FROM zona WHERE sede_id = 1 AND nombre = 'Biblioteca'").fetchone()["id"]
    return {"admin": admin, "estudiante": est, "zona": zona}


def _evento(conn, agregado, fila, tipo_evento):
    conn.execute("INSERT INTO outbox (agregado, agregado_id, sede_id, tipo_evento, payload) VALUES (%s,%s,1,%s,%s)",
                 (agregado, fila["id"], tipo_evento,
                  Jsonb({"id": str(fila["id"]), "creado_en": fila["creado_en"].isoformat()})))


def _reporte(conn, b, descripcion):
    fila = conn.execute(
        "INSERT INTO reporte_perdida (sede_id, estudiante_id, categoria_id, zona_id, descripcion, descripcion_publica, "
        "fecha_perdida, registrado_por) VALUES (1, %s, 7, %s, %s, 'Termo', %s, %s) RETURNING id, creado_en",
        (b["estudiante"], b["zona"], descripcion, date.today(), b["admin"])).fetchone()
    _evento(conn, "reporte_perdida", fila, "reporte.creado")
    return fila


def _hallazgo(conn, b, descripcion):
    fila = conn.execute(
        "INSERT INTO hallazgo (sede_id, categoria_id, zona_id, descripcion, descripcion_publica, fecha_hallazgo, "
        "vence_en, registrado_por) VALUES (1, 7, %s, %s, 'Termo', %s, %s, %s) RETURNING id, creado_en",
        (b["zona"], descripcion, date.today(), date.today(), b["admin"])).fetchone()
    _evento(conn, "hallazgo", fila, "hallazgo.creado")
    return fila


def _verificar(conn, admin, coincidencia_id):
    """Efecto de POST /coincidencias/{id}/verificar en la base (la API lo hace igual)."""
    conn.execute("UPDATE coincidencia SET estado = 'verificada', decidido_por = %s, decidido_en = now() "
                 "WHERE id = %s", (admin, coincidencia_id))
    conn.execute("INSERT INTO outbox (agregado, agregado_id, sede_id, tipo_evento, payload) "
                 "VALUES ('coincidencia', %s, 1, 'coincidencia.verificada', %s)",
                 (coincidencia_id, Jsonb({"id": str(coincidencia_id)})))


def _ciclo(e):
    procesar_lote(e["conn"], e["r"], "matcher", e["matcher"].ejecutar, "prueba")
    procesar_lote(e["conn"], e["r"], "notificador", e["notificador"].ejecutar, "prueba")


def test_flujo_matcher_admin_notificador(entorno):
    conn, b = entorno["conn"], _base(entorno["conn"])
    correcto = _hallazgo(conn, b, "Se encontró termo stanley azul con sticker de un gato")
    distractor = _hallazgo(conn, b, "Se encontró termo contigo negro con la tapa rayada")
    rep = _reporte(conn, b, "Perdí mi termo stanley azul marino con sticker de un gato. "
                            "Mi nombre es Valentina López, cel 310 555 1234")
    _ciclo(entorno)

    # Solo se miran los hallazgos de esta prueba (la base puede tener otros de corridas anteriores)
    sugeridas = conn.execute("SELECT * FROM coincidencia WHERE reporte_id = %s AND hallazgo_id IN (%s, %s)",
                             (rep["id"], correcto["id"], distractor["id"])).fetchall()
    assert [c["hallazgo_id"] for c in sugeridas] == [correcto["id"]]   # el termo negro Contigo no pasa el umbral
    co = sugeridas[0]
    assert co["estado"] == "sugerida" and co["decidido_por"] is None    # la IA nunca decide
    assert co["explicacion"].startswith("[alta]")

    # Al LLM no le llegaron el nombre ni el teléfono del dueño
    todo = " ".join(entorno["chat"].mensajes_recibidos)
    assert "Valentina" not in todo and "López" not in todo and "310" not in todo

    traza = entorno["trazas"].find_one({"agente": "matcher", "disparador.ref": str(rep["id"])})
    assert traza["estado"] == "ok" and traza["llamadas_llm"] >= 2
    assert {"nombre", "telefono"} <= set(traza["datos_personales_eliminados"])
    assert "Valentina" not in json.dumps(traza, default=str)       # la traza tampoco guarda datos personales

    # El admin verifica (lo hace la API; aquí se simula su efecto en la base)
    _verificar(conn, b["admin"], co["id"])
    _ciclo(entorno)

    enviados = entorno["correo"].enviados
    assert len(enviados) == 1 and enviados[0]["destino"] == "vale@pruebas.edu.co"
    cuerpo = enviados[0]["cuerpo"].lower()
    assert "valentina" in cuerpo                                   # saludo con el nombre
    assert "termo" not in cuerpo and "stanley" not in cuerpo and "azul" not in cuerpo   # sin detalles del objeto


def test_reprocesar_eventos_no_duplica(entorno):
    conn, b = entorno["conn"], _base(entorno["conn"])
    hal = _hallazgo(conn, b, "Se encontró termo stanley verde con sticker de la selección Colombia")
    rep = _reporte(conn, b, "Perdí termo stanley verde con sticker de la selección Colombia")
    _ciclo(entorno)
    # Se rebobina el offset: el mismo evento se procesa otra vez (garantía "al menos una vez")
    conn.execute("UPDATE consumidor_outbox SET ultimo_id = ultimo_id - 2 WHERE consumidor = 'matcher'")
    _ciclo(entorno)
    n = conn.execute("SELECT count(*) AS n FROM coincidencia WHERE reporte_id = %s AND hallazgo_id = %s",
                     (rep["id"], hal["id"])).fetchone()["n"]
    assert n == 1


def test_par_rechazado_no_se_vuelve_a_sugerir(entorno):
    conn, b = entorno["conn"], _base(entorno["conn"])
    hal = _hallazgo(conn, b, "Se encontró termo stanley rojo con un pin de Star Wars")
    rep = _reporte(conn, b, "Perdí termo stanley rojo con un pin de Star Wars")
    _ciclo(entorno)
    conn.execute("UPDATE coincidencia SET estado = 'rechazada', decidido_por = %s, decidido_en = now(), "
                 "motivo_rechazo = 'No es' WHERE reporte_id = %s", (b["admin"], rep["id"]))
    # Llega otro evento del mismo hallazgo (p. ej. se reindexó): el par rechazado no reaparece
    _evento(conn, "hallazgo", hal, "hallazgo.creado")
    _ciclo(entorno)
    estados = [f["estado"] for f in conn.execute(
        "SELECT estado FROM coincidencia WHERE reporte_id = %s AND hallazgo_id = %s", (rep["id"], hal["id"]))]
    assert estados == ["rechazada"]


def test_sin_consentimiento_no_hay_correo(entorno):
    conn, b = entorno["conn"], _base(entorno["conn"])
    conn.execute("UPDATE consentimiento SET finalidades = '{gestion_objeto}' WHERE estudiante_id = %s",
                 (b["estudiante"],))
    hal = _hallazgo(conn, b, "Se encontró termo stanley amarillo con las iniciales bordadas")
    rep = _reporte(conn, b, "Perdí termo stanley amarillo con las iniciales bordadas")
    _ciclo(entorno)
    co = conn.execute("SELECT id FROM coincidencia WHERE reporte_id = %s AND hallazgo_id = %s",
                      (rep["id"], hal["id"])).fetchone()
    _verificar(conn, b["admin"], co["id"])
    _ciclo(entorno)
    assert entorno["correo"].enviados == []
    traza = entorno["trazas"].find_one({"agente": "notificador", "disparador.ref": str(co["id"])})
    assert traza["salida"]["motivo"].startswith("sin consentimiento")


def test_limite_de_llamadas_corta_la_ejecucion(entorno):
    from harness.nucleo import Limites

    conn, b = entorno["conn"], _base(entorno["conn"])
    entorno["matcher"].limites = Limites(max_llamadas_llm=0, max_tokens=8000, max_segundos=120)
    _reporte(conn, b, "Perdí termo stanley gris con un rayón en la esquina")
    _ciclo(entorno)
    traza = entorno["trazas"].find_one({"agente": "matcher", "estado": "limite_excedido"})
    assert traza is not None and "llamadas" in traza["error"]
