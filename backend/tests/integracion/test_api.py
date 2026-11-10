"""Pruebas de la API de punta a punta contra PostgreSQL real (Redis simulado con fakeredis).

    PRUEBAS_INTEGRACION=1 DATABASE_URL=postgresql://... pytest tests/integracion
Usan datos sintéticos con identificadores únicos, así que pueden correr sobre una base con datos.
"""

import os
import uuid
from datetime import date, timedelta

import fakeredis
import psycopg
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(
    os.environ.get("PRUEBAS_INTEGRACION") != "1", reason="requiere PostgreSQL (PRUEBAS_INTEGRACION=1)"
)

CLAVE = "clave-de-prueba-123"
CAMPOS_PUBLICOS = {"tipo", "id", "categoria", "zona", "descripcion", "fecha", "estado", "publicado_en"}


@pytest.fixture(scope="module")
def entorno():
    os.environ["COOKIE_SEGURA"] = "false"   # TestClient usa http://testserver
    os.environ["SECRET_KEY"] = "clave-de-pruebas-" + "x" * 40
    from app.cache import get_redis
    from app.config import get_settings
    from app.main import app
    from app.seguridad import hashear

    get_settings.cache_clear()
    falso = fakeredis.FakeRedis(decode_responses=True)
    app.dependency_overrides[get_redis] = lambda: falso

    sufijo = uuid.uuid4().hex[:8]
    usuarios = {}
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute("INSERT INTO sede (id, codigo, nombre, ciudad) VALUES (2, 'SEDE-02', 'Sede prueba', 'Soacha') "
                     "ON CONFLICT (id) DO NOTHING")
        conn.execute("INSERT INTO zona (sede_id, nombre) VALUES (2, 'Biblioteca') ON CONFLICT DO NOTHING")
        cuentas = (("admin1", "admin_sede", 1), ("admin2", "admin_sede", 2), ("auditor", "auditor", None))
        for nombre, rol, sede in cuentas:
            email = f"{nombre}-{sufijo}@pruebas.uniminuto.edu.co"
            conn.execute("INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) VALUES (%s,%s,%s,%s,%s)",
                         (sede, email, nombre, hashear(CLAVE), rol))
            usuarios[nombre] = email
        biblioteca = conn.execute("SELECT id FROM zona WHERE sede_id = 1 AND nombre = 'Biblioteca'").fetchone()[0]
    yield {"app": app, "usuarios": usuarios, "redis": falso, "zona": biblioteca, "sufijo": sufijo}
    app.dependency_overrides.clear()
    os.environ.pop("COOKIE_SEGURA", None)
    os.environ.pop("SECRET_KEY", None)
    get_settings.cache_clear()


def cliente(entorno, quien: str | None = None) -> TestClient:
    c = TestClient(entorno["app"])
    if quien:
        r = c.post("/api/v1/auth/login", json={"email": entorno["usuarios"][quien], "contrasena": CLAVE})
        assert r.status_code == 200, r.text
        assert "token" not in r.json()            # el token solo viaja en la cookie httpOnly
    return c


def nuevo_estudiante(c: TestClient, con_consentimiento=True) -> str:
    doc = str(uuid.uuid4().int)[:10]
    r = c.post("/api/v1/estudiantes", json={
        "tipo_documento": "CC", "numero_documento": doc, "nombres": "Laura", "apellidos": "Martínez",
        "correo_institucional": "laura@pruebas.uniminuto.edu.co"})
    assert r.status_code == 201, r.text
    est = r.json()["id"]
    if con_consentimiento:
        r = c.post("/api/v1/consentimientos", json={"estudiante_id": est,
                                                      "finalidades": ["gestion_objeto", "notificacion_correo"]})
        assert r.status_code == 201, r.text
    return est


def nuevo_reporte(c: TestClient, entorno, est: str, clave: str | None = None):
    return c.post("/api/v1/reportes", headers={"Idempotency-Key": clave or uuid.uuid4().hex}, json={
        "estudiante_id": est, "categoria_id": 7, "zona_id": entorno["zona"],
        "descripcion": "Termo Stanley azul de Laura Martínez con sticker de un gato",
        "descripcion_publica": "Termo azul con sticker", "detalle_control": "sticker de un gato",
        "fecha_perdida": date.today().isoformat(),
    })


def nuevo_hallazgo(c: TestClient, entorno):
    return c.post("/api/v1/hallazgos", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
        "categoria_id": 7, "zona_id": entorno["zona"], "descripcion": "Termo azul con sticker de gato",
        "descripcion_publica": "Termo azul", "fecha_hallazgo": date.today().isoformat(),
        "encontrado_por": "Estudiante de turno", "ubicacion_bodega": "Estante A3",
    })


def sugerir(reporte: dict, hallazgo: dict) -> str:
    """Simula al agente matcher: inserta una coincidencia 'sugerida'."""
    from app.config import get_settings

    with psycopg.connect(get_settings().database_url) as conn:
        return str(conn.execute(
            "INSERT INTO coincidencia (sede_id, reporte_id, reporte_creado_en, hallazgo_id, hallazgo_creado_en, "
            "similitud, puntaje, explicacion, modelo_embedding) VALUES (1,%s,%s,%s,%s,0.93,0.91,'Mismo color y tipo',"
            "'bge-m3') RETURNING id",
            (reporte["id"], reporte["creado_en"], hallazgo["id"], hallazgo["creado_en"]),
        ).fetchone()[0])


# ---------------------------------------------------------------------------------------- pruebas
def test_sin_sesion_no_hay_acceso(entorno):
    c = cliente(entorno)
    assert c.get("/api/v1/reportes").status_code == 401
    assert c.get("/api/v1/reportes").json()["codigo"] == "no_autenticado"


def test_login_bloquea_tras_cinco_intentos(entorno):
    from app.config import get_settings
    from app.seguridad import hashear

    email = f"bloqueo-{uuid.uuid4().hex[:6]}@pruebas.uniminuto.edu.co"
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute("INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) VALUES (1,%s,'x',%s,"
                     "'admin_sede')", (email, hashear(CLAVE)))
    c = TestClient(entorno["app"])
    for _ in range(5):
        assert c.post("/api/v1/auth/login", json={"email": email, "contrasena": "mala"}).status_code == 401
    r = c.post("/api/v1/auth/login", json={"email": email, "contrasena": CLAVE})
    assert r.status_code == 423                                # bloqueada aunque ahora la clave sea correcta
    with psycopg.connect(get_settings().database_url) as conn:
        fallidos = conn.execute("SELECT count(*) FROM auditoria a JOIN usuario u ON u.id = a.usuario_id "
                                "WHERE u.email = %s AND a.accion = 'login_fallido'", (email,)).fetchone()[0]
    assert fallidos == 5                                       # los intentos fallidos quedaron auditados


def test_reporte_exige_consentimiento(entorno):
    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c, con_consentimiento=False)
    r = nuevo_reporte(c, entorno, est)
    assert r.status_code == 409 and "consentimiento" in r.json()["mensaje"]


def test_idempotencia_no_duplica(entorno):
    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c)
    clave = uuid.uuid4().hex
    a, b = nuevo_reporte(c, entorno, est, clave), nuevo_reporte(c, entorno, est, clave)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"]


def test_flujo_completo_hasta_la_entrega(entorno):
    from app.config import get_settings

    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c)
    rep = nuevo_reporte(c, entorno, est).json()
    hal = nuevo_hallazgo(c, entorno).json()
    assert hal["vence_en"] == (date.today() + timedelta(days=90)).isoformat()
    coin = sugerir(rep, hal)

    bandeja = c.get("/api/v1/coincidencias").json()["items"]
    assert coin in [x["id"] for x in bandeja]

    assert c.post(f"/api/v1/coincidencias/{coin}/verificar").json()["estado"] == "verificada"
    assert c.post(f"/api/v1/coincidencias/{coin}/verificar").status_code == 409   # no se decide dos veces

    fallida = c.post("/api/v1/entregas", json={"coincidencia_id": coin, "verificacion_ok": False,
                                                "numero_acta": "ACTA-1"}).json()
    assert fallida["entregado"] is False                                         # sigue en custodia

    ok = c.post("/api/v1/entregas", json={"coincidencia_id": coin, "verificacion_ok": True, "numero_acta": "ACTA-2"})
    assert ok.status_code == 200 and ok.json()["estado_caso"] == "cerrado"

    with psycopg.connect(get_settings().database_url) as conn:
        estados = conn.execute(
            "SELECT (SELECT estado FROM reporte_perdida WHERE id = %s), (SELECT estado FROM hallazgo WHERE id = %s), "
            "(SELECT estado FROM coincidencia WHERE id = %s)", (rep["id"], hal["id"], coin)).fetchone()
        eventos = {f[0] for f in conn.execute(
            "SELECT tipo_evento FROM outbox WHERE agregado_id IN (%s, %s, %s)", (rep["id"], hal["id"], coin))}
        payloads = " ".join(str(f[0]) for f in conn.execute(
            "SELECT payload FROM outbox WHERE agregado_id IN (%s, %s, %s)", (rep["id"], hal["id"], coin)))
    assert estados == ("cerrado", "cerrado", "entregada")
    assert {"reporte.creado", "hallazgo.creado", "coincidencia.verificada"} <= eventos
    assert "Laura" not in payloads and "Martínez" not in payloads                # outbox sin datos personales

    # Un caso cerrado desaparece de la página pública
    publico = TestClient(entorno["app"]).get(f"/api/v1/publico/objetos/{rep['id']}")
    assert publico.status_code == 404


def test_rechazo_exige_motivo(entorno):
    c = cliente(entorno, "admin1")
    rep = nuevo_reporte(c, entorno, nuevo_estudiante(c)).json()
    coin = sugerir(rep, nuevo_hallazgo(c, entorno).json())
    assert c.post(f"/api/v1/coincidencias/{coin}/rechazar", json={"motivo": ""}).status_code == 422
    r = c.post(f"/api/v1/coincidencias/{coin}/rechazar", json={"motivo": "Otro color"})
    assert r.json()["estado"] == "rechazada"


def test_vista_publica_sin_datos_personales_y_paginada(entorno):
    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c)
    for _ in range(3):
        assert nuevo_reporte(c, entorno, est).status_code == 201
    entorno["redis"].flushall()                                  # sin caché ni límite acumulado

    p = TestClient(entorno["app"])
    pagina1 = p.get("/api/v1/publico/objetos", params={"tipo": "perdido", "categoria": "botellas", "limite": 2}).json()
    assert len(pagina1["items"]) == 2 and pagina1["siguiente"]
    for item in pagina1["items"]:
        assert set(item) == CAMPOS_PUBLICOS                      # lista blanca exacta (ADR-007)
    texto = str(pagina1)
    assert "Laura" not in texto and "sticker de un gato" not in texto   # ni dueño ni detalle de control
    pagina2 = p.get("/api/v1/publico/objetos", params={"tipo": "perdido", "categoria": "botellas", "limite": 2,
                                                         "cursor": pagina1["siguiente"]}).json()
    ids1 = {i["id"] for i in pagina1["items"]}
    assert ids1.isdisjoint({i["id"] for i in pagina2["items"]})  # el cursor no repite resultados


def test_limite_de_peticiones_publicas(entorno):
    entorno["redis"].flushall()
    p = TestClient(entorno["app"])
    codigos = [p.get("/api/v1/publico/objetos", params={"limite": 1}).status_code for _ in range(61)]
    assert codigos[:60] == [200] * 60 and codigos[60] == 429
    entorno["redis"].flushall()


def test_admin_de_otra_sede_no_ve_el_reporte(entorno):
    c1 = cliente(entorno, "admin1")
    rep = nuevo_reporte(c1, entorno, nuevo_estudiante(c1)).json()
    c2 = cliente(entorno, "admin2")
    assert c2.get(f"/api/v1/reportes/{rep['id']}").status_code == 404


def test_lectura_de_datos_personales_queda_auditada(entorno):
    c = cliente(entorno, "admin1")
    rep = nuevo_reporte(c, entorno, nuevo_estudiante(c)).json()
    detalle = c.get(f"/api/v1/reportes/{rep['id']}").json()
    assert detalle["nombres"] == "Laura" and detalle["detalle_control"] == "sticker de un gato"

    assert c.get("/api/v1/auditoria").status_code == 403          # un admin no lee la auditoría
    aud = cliente(entorno, "auditor").get("/api/v1/auditoria", params={"entidad_id": rep["id"], "accion": "leer"})
    assert aud.status_code == 200 and len(aud.json()["items"]) == 1


def test_anonimizar_borra_datos_personales(entorno):
    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c)
    rep = nuevo_reporte(c, entorno, est).json()
    assert c.post(f"/api/v1/estudiantes/{est}/anonimizar").json()["anonimizado"] is True
    detalle = c.get(f"/api/v1/reportes/{rep['id']}").json()
    assert detalle["nombres"] == "Anonimizado" and detalle["correo_institucional"] is None
    assert "Laura" not in detalle["descripcion"] and detalle["detalle_control"] is None
    assert nuevo_reporte(c, entorno, est).status_code == 409     # sin consentimiento vigente


def test_ip_falsa_en_encabezado_no_rompe_la_auditoria(entorno):
    entorno["redis"].flushall()
    c = TestClient(entorno["app"], headers={"X-Forwarded-For": "'; DROP TABLE auditoria; --"})
    r = c.post("/api/v1/auth/login", json={"email": entorno["usuarios"]["admin1"], "contrasena": CLAVE})
    assert r.status_code == 200


def test_analitica_por_sede_y_roles(entorno):
    from app.config import get_settings

    with psycopg.connect(get_settings().database_url) as conn:
        for sede, texto in ((1, "informe sede 1"), (2, "informe sede 2"), (None, "informe global")):
            conn.execute("INSERT INTO informe_analitica (sede_id, datos_hasta, metricas, prediccion, resumen, "
                         "resumen_fuente, ejecucion_id) VALUES (%s, current_date, '{\"mes\": {}}', "
                         "'{\"semanas\": []}', %s, 'plantilla', 'prueba')", (sede, texto))
    assert TestClient(entorno["app"]).get("/api/v1/analitica/resumen").status_code == 401
    a1 = cliente(entorno, "admin1")
    assert a1.get("/api/v1/analitica/resumen").json()["resumen"] == "informe sede 1"
    assert a1.get("/api/v1/analitica/resumen", params={"alcance": "global"}).json()["resumen"] == "informe global"
    assert a1.get("/api/v1/analitica/resumen", params={"sede_id": 2}).status_code == 403   # otra sede
    aud = cliente(entorno, "auditor")
    assert aud.get("/api/v1/analitica/resumen", params={"sede_id": 2}).json()["resumen"] == "informe sede 2"
    assert aud.get("/api/v1/analitica/resumen").json()["resumen"] == "informe global"
    assert aud.get("/api/v1/analitica/resumen", params={"sede_id": 99}).json()["codigo"] == "sin_informe"


def test_hallazgos_no_se_publican(entorno):
    """ADR-016: publicar lo encontrado atrae falsos dueños; solo se publica lo perdido."""
    c = cliente(entorno, "admin1")
    hal = nuevo_hallazgo(c, entorno).json()
    rep = nuevo_reporte(c, entorno, nuevo_estudiante(c)).json()
    entorno["redis"].flushall()
    p = TestClient(entorno["app"])
    assert p.get(f"/api/v1/publico/objetos/{hal['id']}").status_code == 404
    assert p.get(f"/api/v1/publico/objetos/{rep['id']}").status_code == 200
    items = p.get("/api/v1/publico/objetos", params={"limite": 50}).json()["items"]
    assert items and {i["tipo"] for i in items} == {"perdido"}
    entorno["redis"].flushall()


def _cuenta_nueva(clave=CLAVE) -> str:
    from app.config import get_settings
    from app.seguridad import hashear

    email = f"clave-{uuid.uuid4().hex[:8]}@pruebas.uniminuto.edu.co"
    with psycopg.connect(get_settings().database_url) as conn:
        conn.execute("INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) "
                     "VALUES (1, %s, 'Admin prueba', %s, 'admin_sede')", (email, hashear(clave)))
    return email


def test_olvide_y_restablecer_contrasena(entorno, monkeypatch):

    from app import correo

    enviados = []
    monkeypatch.setattr(correo, "enviar", lambda para, asunto, cuerpo: enviados.append((para, cuerpo)))
    entorno["redis"].flushall()
    email = _cuenta_nueva()
    p = TestClient(entorno["app"])

    # La respuesta es idéntica exista o no el correo (no revela cuentas)
    r_no = p.post("/api/v1/auth/olvide-contrasena", json={"email": "nadie@pruebas.uniminuto.edu.co"})
    r_si = p.post("/api/v1/auth/olvide-contrasena", json={"email": email})
    assert r_no.status_code == r_si.status_code == 202 and r_no.json() == r_si.json()
    assert len(enviados) == 1 and enviados[0][0] == email
    assert "/admin/restablecer?token=" in enviados[0][1]
    entorno["redis"].flushall()


def test_restablecer_un_solo_uso_y_desbloquea(entorno, monkeypatch):
    import re

    from app import correo

    enviados = []
    monkeypatch.setattr(correo, "enviar", lambda para, asunto, cuerpo: enviados.append(cuerpo))
    entorno["redis"].flushall()
    email = _cuenta_nueva()
    p = TestClient(entorno["app"])
    for _ in range(5):
        p.post("/api/v1/auth/login", json={"email": email, "contrasena": "mala"})
    assert p.post("/api/v1/auth/login", json={"email": email, "contrasena": CLAVE}).status_code == 423

    p.post("/api/v1/auth/olvide-contrasena", json={"email": email})
    token = re.search(r"token=([\w-]+)", enviados[-1]).group(1)
    debil = p.post("/api/v1/auth/restablecer-contrasena", json={"token": token, "contrasena": "corta"})
    assert debil.status_code == 422          # mínimo 12 caracteres; el enlace NO se gasta (la transacción se revierte)
    nueva = "otra-clave-larga-2026"
    assert p.post("/api/v1/auth/restablecer-contrasena",
                  json={"token": token, "contrasena": nueva}).status_code == 200
    assert p.post("/api/v1/auth/restablecer-contrasena",
                  json={"token": token, "contrasena": nueva + "x"}).json()["codigo"] == "enlace_invalido"
    assert p.post("/api/v1/auth/login", json={"email": email, "contrasena": nueva}).status_code == 200
    assert p.post("/api/v1/auth/login", json={"email": email, "contrasena": CLAVE}).status_code == 401

    # Pedir un enlace nuevo anula el anterior; un enlace vencido no sirve
    p.post("/api/v1/auth/olvide-contrasena", json={"email": email})
    viejo = re.search(r"token=([\w-]+)", enviados[-1]).group(1)
    p.post("/api/v1/auth/olvide-contrasena", json={"email": email})
    assert p.post("/api/v1/auth/restablecer-contrasena",
                  json={"token": viejo, "contrasena": "clave-nueva-numero-3"}).status_code == 400
    entorno["redis"].flushall()


def test_cambiar_contrasena_con_sesion(entorno):
    email = _cuenta_nueva()
    p = TestClient(entorno["app"])
    p.post("/api/v1/auth/login", json={"email": email, "contrasena": CLAVE})
    assert p.post("/api/v1/auth/cambiar-contrasena",
                  json={"actual": "equivocada", "nueva": "clave-nueva-larga-1"}).status_code == 400
    assert p.post("/api/v1/auth/cambiar-contrasena",
                  json={"actual": CLAVE, "nueva": "clave-nueva-larga-1"}).status_code == 200
    assert TestClient(entorno["app"]).post("/api/v1/auth/cambiar-contrasena",
                                           json={"actual": "x", "nueva": "y"}).status_code == 401


def test_restablecer_desde_consola(entorno, monkeypatch, capsys):
    import re
    import sys

    from app import crear_usuario

    email = _cuenta_nueva()
    monkeypatch.setattr(sys, "argv", ["crear_usuario", "--restablecer", "--email", email])
    assert crear_usuario.main() == 0
    token = re.search(r"token=([\w-]+)", capsys.readouterr().out).group(1)
    p = TestClient(entorno["app"])
    assert p.post("/api/v1/auth/restablecer-contrasena",
                  json={"token": token, "contrasena": "desde-la-consola-2026"}).status_code == 200
    assert p.post("/api/v1/auth/login", json={"email": email, "contrasena": "desde-la-consola-2026"}).status_code == 200
