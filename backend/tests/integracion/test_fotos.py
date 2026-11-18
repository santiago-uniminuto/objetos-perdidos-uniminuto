"""Fotos (ADR-018) contra PostgreSQL real; el almacén es una carpeta temporal en vez de SeaweedFS."""

import io
import os
import uuid
from datetime import date

import psycopg
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tests.integracion.test_api import cliente, nuevo_estudiante, nuevo_hallazgo, nuevo_reporte, sugerir

pytestmark = pytest.mark.skipif(
    os.environ.get("PRUEBAS_INTEGRACION") != "1", reason="requiere PostgreSQL (PRUEBAS_INTEGRACION=1)"
)


def foto_jpeg(color=(30, 90, 200), lado=2400, con_gps=True) -> bytes:
    """Foto sintética con metadatos EXIF (incluido GPS) para comprobar que se eliminan."""
    img = Image.new("RGB", (lado, lado * 3 // 4), color)
    exif = Image.Exif()
    exif[0x010F] = "MarcaDelCelular"           # Make
    if con_gps:
        exif[0x8825] = {1: "N", 2: (4.0, 41.0, 0.0), 3: "W", 4: (74.0, 5.0, 0.0)}  # GPSInfo: Bogotá
    salida = io.BytesIO()
    img.save(salida, "JPEG", exif=exif, quality=90)
    return salida.getvalue()


def subir(c, coleccion, objeto_id, datos, nombre="foto.jpg", tipo="image/jpeg"):
    return c.post(f"/api/v1/{coleccion}/{objeto_id}/fotos", files={"archivo": (nombre, datos, tipo)})


def test_foto_de_perdido_es_publica_y_sin_metadatos(entorno):
    c = cliente(entorno, "admin1")
    rep = nuevo_reporte(c, entorno, nuevo_estudiante(c)).json()
    r = subir(c, "reportes", rep["id"], foto_jpeg())
    assert r.status_code == 201, r.text
    foto = r.json()
    assert foto["orden"] == 1 and max(foto["ancho"], foto["alto"]) == 1600   # se reduce a 1600 px

    entorno["redis"].flushall()
    p = TestClient(entorno["app"])
    publico = p.get(f"/api/v1/publico/objetos/{rep['id']}").json()
    assert publico["fotos"] == [foto["id"]]
    img = p.get(f"/api/v1/publico/fotos/{foto['id']}/mini")
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
    abierta = Image.open(io.BytesIO(img.content))
    assert max(abierta.size) == 480
    assert not abierta.getexif() and b"MarcaDelCelular" not in img.content   # sin EXIF ni GPS
    grande = c.get(f"/api/v1/fotos/{foto['id']}/grande")
    assert grande.status_code == 200 and b"MarcaDelCelular" not in grande.content
    assert c.get(f"/api/v1/reportes/{rep['id']}").json()["fotos"][0]["id"] == foto["id"]
    entorno["redis"].flushall()


def test_foto_de_hallazgo_nunca_es_publica(entorno):
    c = cliente(entorno, "admin1")
    hal = nuevo_hallazgo(c, entorno).json()
    foto = subir(c, "hallazgos", hal["id"], foto_jpeg((200, 40, 40))).json()
    entorno["redis"].flushall()
    p = TestClient(entorno["app"])
    assert p.get(f"/api/v1/publico/fotos/{foto['id']}/mini").status_code == 404
    assert c.get(f"/api/v1/fotos/{foto['id']}/mini").status_code == 200     # el admin sí la ve
    assert c.get(f"/api/v1/hallazgos/{hal['id']}").json()["fotos"][0]["id"] == foto["id"]
    entorno["redis"].flushall()


def test_foto_de_documento_nunca_es_publica(entorno):
    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c)
    rep = c.post("/api/v1/reportes", headers={"Idempotency-Key": uuid.uuid4().hex}, json={
        "estudiante_id": est, "categoria_id": 2, "zona_id": entorno["zona"], "descripcion": "Carné estudiantil",
        "descripcion_publica": "Carné estudiantil", "fecha_perdida": date.today().isoformat()}).json()
    foto = subir(c, "reportes", rep["id"], foto_jpeg((240, 240, 240))).json()
    entorno["redis"].flushall()
    p = TestClient(entorno["app"])
    assert p.get(f"/api/v1/publico/objetos/{rep['id']}").json()["fotos"] == []
    assert p.get(f"/api/v1/publico/fotos/{foto['id']}/mini").status_code == 404
    entorno["redis"].flushall()


def test_limites_y_validaciones(entorno):
    c = cliente(entorno, "admin1")
    rep = nuevo_reporte(c, entorno, nuevo_estudiante(c)).json()
    assert subir(c, "reportes", rep["id"], b"esto no es una imagen", "x.jpg").status_code == 415
    primera = foto_jpeg((10, 10, 10), lado=800)
    assert subir(c, "reportes", rep["id"], primera).status_code == 201
    assert subir(c, "reportes", rep["id"], primera).status_code == 409             # la misma foto otra vez
    for color in ((20, 20, 20), (40, 40, 40)):
        assert subir(c, "reportes", rep["id"], foto_jpeg(color, lado=800)).status_code == 201
    cuarta = subir(c, "reportes", rep["id"], foto_jpeg((60, 60, 60), lado=800))
    assert cuarta.status_code == 409 and "3 fotos" in cuarta.json()["mensaje"]
    # Borrar libera el lugar y el orden se reutiliza
    fotos = c.get(f"/api/v1/reportes/{rep['id']}").json()["fotos"]
    assert c.delete(f"/api/v1/fotos/{fotos[1]['id']}").status_code == 204
    assert subir(c, "reportes", rep["id"], foto_jpeg((60, 60, 60), lado=800)).json()["orden"] == 2
    # Otra sede no ve ni borra
    c2 = cliente(entorno, "admin2")
    assert c2.get(f"/api/v1/fotos/{fotos[0]['id']}/mini").status_code == 404
    assert subir(c2, "reportes", rep["id"], foto_jpeg((70, 70, 70), lado=800)).status_code == 404
    assert TestClient(entorno["app"]).post(f"/api/v1/reportes/{rep['id']}/fotos").status_code == 401


def test_anonimizar_y_purga_borran_fotos(entorno):
    from app.config import get_settings
    from app.modulos.fotos import purgar

    c = cliente(entorno, "admin1")
    est = nuevo_estudiante(c)
    rep = nuevo_reporte(c, entorno, est).json()
    foto = subir(c, "reportes", rep["id"], foto_jpeg((90, 20, 120), lado=800)).json()
    assert c.post(f"/api/v1/estudiantes/{est}/anonimizar").status_code == 200
    assert c.get(f"/api/v1/fotos/{foto['id']}/mini").status_code == 404

    hal = nuevo_hallazgo(c, entorno).json()
    vieja = subir(c, "hallazgos", hal["id"], foto_jpeg((5, 120, 60), lado=800)).json()
    with psycopg.connect(get_settings().database_url, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("UPDATE hallazgo SET estado = 'entregado', cerrado_en = now() - interval '91 days' "
                     "WHERE id = %s", (hal["id"],))
        assert purgar(conn) >= 1
        assert not conn.execute("SELECT 1 FROM foto_objeto WHERE id = %s", (vieja["id"],)).fetchone()


def test_acta_numerada_impresa_y_firmada(entorno):
    from app.config import get_settings

    c, otra = cliente(entorno, "admin1"), cliente(entorno, "admin2")
    numeros = []
    for _ in range(2):
        coin = sugerir(nuevo_reporte(c, entorno, nuevo_estudiante(c)).json(), nuevo_hallazgo(c, entorno).json())
        assert c.post(f"/api/v1/coincidencias/{coin}/verificar").status_code == 200
        r = c.post("/api/v1/entregas", json={"coincidencia_id": coin, "verificacion_ok": True}).json()
        numeros.append((r["entrega_id"], r["numero_acta"]))
    (eid, n1), (_, n2) = numeros
    assert int(n2[-5:]) == int(n1[-5:]) + 1 and n1[:-5] == n2[:-5]            # consecutivo por sede y año

    # El acta para imprimir trae al dueño y el objeto; la lectura queda auditada; otra sede no la ve
    acta = c.get(f"/api/v1/entregas/{eid}/acta").json()
    assert acta["numero_acta"] == n1 and acta["nombres"] == "Laura" and acta["numero_documento"]
    assert acta["firmada"] is False and acta["categoria"] and acta["entregado_por"] == "admin1"
    assert otra.get(f"/api/v1/entregas/{eid}/acta").status_code == 404
    with psycopg.connect(get_settings().database_url) as conn:
        assert conn.execute("SELECT count(*) FROM auditoria WHERE entidad = 'entrega' AND entidad_id = %s "
                            "AND accion = 'leer'", (eid,)).fetchone()[0] >= 1

    # Registro: sin datos del dueño; pendiente de firma hasta que se sube la foto del acta firmada
    lista = c.get("/api/v1/entregas?firma=pendiente&limite=100").json()
    fila = next(x for x in lista["items"] if x["id"] == eid)
    assert fila["numero_acta"] == n1 and "nombres" not in fila and lista["sin_firma"] >= 2
    assert c.get(f"/api/v1/entregas/{eid}/acta-firmada/mini").status_code == 404
    r = c.post(f"/api/v1/entregas/{eid}/acta-firmada", files={"archivo": ("acta.jpg", foto_jpeg(), "image/jpeg")})
    assert r.status_code == 201, r.text
    img = c.get(f"/api/v1/entregas/{eid}/acta-firmada/grande")
    assert img.status_code == 200 and b"MarcaDelCelular" not in img.content     # sin EXIF ni GPS
    assert otra.get(f"/api/v1/entregas/{eid}/acta-firmada/grande").status_code == 404
    assert eid in [x["id"] for x in c.get("/api/v1/entregas?firma=firmada&limite=100").json()["items"]]
    assert c.get(f"/api/v1/entregas/{eid}/acta").json()["firmada"] is True
