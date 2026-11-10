"""Pruebas del esquema contra un PostgreSQL real con la migración aplicada.

Se ejecutan solo si PRUEBAS_INTEGRACION=1 (el CI las corre en cada PR):
    PRUEBAS_INTEGRACION=1 DATABASE_URL=postgresql://... pytest tests/integracion
Cada prueba corre dentro de una transacción que se revierte: no deja basura.
"""

import os
import uuid
from datetime import date

import psycopg
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("PRUEBAS_INTEGRACION") != "1", reason="requiere PostgreSQL (PRUEBAS_INTEGRACION=1)"
)

COLUMNAS_PERSONALES = {
    "nombres", "apellidos", "numero_documento", "tipo_documento", "correo_institucional",
    "telefono", "estudiante_id", "encontrado_por", "detalle_control", "descripcion", "foto_clave",
}


@pytest.fixture
def db():
    url = os.environ.get("DATABASE_URL", "postgresql://app:app@localhost:5432/objetos_perdidos")
    with psycopg.connect(url) as conn:
        yield conn
        conn.rollback()


@pytest.fixture
def base(db):
    """Crea un admin y un estudiante de prueba (sintéticos)."""
    admin = db.execute(
        "INSERT INTO usuario (sede_id, email, nombre, hash_contrasena, rol) "
        "VALUES (1, %s, 'Admin Prueba', 'x', 'admin_sede') RETURNING id",
        (f"admin-{uuid.uuid4()}@prueba.local",),
    ).fetchone()[0]
    estudiante = db.execute(
        "INSERT INTO estudiante (tipo_documento, numero_documento, nombres, apellidos) "
        "VALUES ('CC', %s, 'Ana', 'Prueba') RETURNING id",
        (str(uuid.uuid4().int)[:10],),
    ).fetchone()[0]
    return {"admin": admin, "estudiante": estudiante}


def _reporte(db, base, estado="publicado"):
    return db.execute(
        "INSERT INTO reporte_perdida (sede_id, estudiante_id, categoria_id, zona_id, descripcion, "
        "descripcion_publica, fecha_perdida, estado, registrado_por) "
        "VALUES (1, %s, 7, (SELECT id FROM zona WHERE sede_id = 1 AND nombre='Biblioteca'), "
        "'Termo azul Stanley de Ana, con sticker', 'Termo azul', %s, %s, %s) "
        "RETURNING id, creado_en",
        (base["estudiante"], date.today(), estado, base["admin"]),
    ).fetchone()


def _hallazgo(db, base):
    return db.execute(
        "INSERT INTO hallazgo (sede_id, categoria_id, descripcion, descripcion_publica, "
        "fecha_hallazgo, vence_en, registrado_por) "
        "VALUES (1, 7, 'Termo azul con sticker', 'Termo azul', %s, %s, %s) RETURNING id, creado_en",
        (date.today(), date.today(), base["admin"]),
    ).fetchone()


def test_semillas_cargadas(db):
    assert db.execute("SELECT count(*) FROM zona WHERE sede_id = 1").fetchone()[0] == 11
    assert db.execute("SELECT count(*) FROM categoria").fetchone()[0] == 8
    assert db.execute("SELECT es_documento FROM categoria WHERE codigo='documentos'").fetchone()[0]


def test_reporte_cae_en_particion_del_mes(db, base):
    rid, _ = _reporte(db, base)
    particion = db.execute(
        "SELECT tableoid::regclass::text FROM reporte_perdida WHERE id = %s", (rid,)
    ).fetchone()[0]
    assert particion == f"reporte_perdida_{date.today():%Y_%m}"


def test_vista_publica_sin_columnas_personales(db, base):
    _reporte(db, base)
    cur = db.execute("SELECT * FROM vista_publica_objetos LIMIT 1")
    columnas = {c.name for c in cur.description}
    assert columnas.isdisjoint(COLUMNAS_PERSONALES), columnas & COLUMNAS_PERSONALES
    fila = dict(zip([c.name for c in cur.description], cur.fetchone(), strict=True))
    assert "Ana" not in str(fila)


def test_vista_publica_oculta_cerrados(db, base):
    rid, _ = _reporte(db, base, estado="cerrado")
    n = db.execute("SELECT count(*) FROM vista_publica_objetos WHERE id = %s", (rid,)).fetchone()[0]
    assert n == 0


def test_auditoria_es_inmutable(db, base):
    db.execute(
        "INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id) "
        "VALUES (%s, 'leer', 'estudiante', %s)",
        (base["admin"], base["estudiante"]),
    )
    with pytest.raises(psycopg.errors.RaiseException, match="solo de insercion"):
        db.execute("UPDATE auditoria SET motivo = 'borrar huella' WHERE usuario_id = %s", (base["admin"],))


def test_coincidencia_no_se_verifica_sin_humano(db, base):
    rid, rc = _reporte(db, base)
    hid, hc = _hallazgo(db, base)
    with pytest.raises(psycopg.errors.CheckViolation, match="decision_humana"):
        db.execute(
            "INSERT INTO coincidencia (sede_id, reporte_id, reporte_creado_en, hallazgo_id, "
            "hallazgo_creado_en, similitud, puntaje, modelo_embedding, estado) "
            "VALUES (1, %s, %s, %s, %s, 0.91, 0.88, 'bge-m3', 'verificada')",
            (rid, rc, hid, hc),
        )


def test_flujo_completo_hasta_entrega(db, base):
    rid, rc = _reporte(db, base)
    hid, hc = _hallazgo(db, base)
    cid = db.execute(
        "INSERT INTO coincidencia (sede_id, reporte_id, reporte_creado_en, hallazgo_id, "
        "hallazgo_creado_en, similitud, puntaje, modelo_embedding) "
        "VALUES (1, %s, %s, %s, %s, 0.91, 0.88, 'bge-m3') RETURNING id",
        (rid, rc, hid, hc),
    ).fetchone()[0]
    db.execute(
        "UPDATE coincidencia SET estado='verificada', decidido_por=%s, decidido_en=now() WHERE id=%s",
        (base["admin"], cid),
    )
    db.execute(
        "INSERT INTO entrega (sede_id, coincidencia_id, estudiante_id, verificacion_ok, numero_acta, "
        "registrado_por) VALUES (1, %s, %s, true, 'ACTA-0001', %s)",
        (cid, base["estudiante"], base["admin"]),
    )
    assert db.execute("SELECT count(*) FROM entrega WHERE coincidencia_id=%s", (cid,)).fetchone()[0] == 1


def test_busqueda_vectorial_ordena_por_similitud(db, base):
    hid, _ = _hallazgo(db, base)
    otro, _ = _hallazgo(db, base)
    v_termo = [1.0] + [0.0] * 1023
    v_otro = [0.0, 1.0] + [0.0] * 1022
    for oid, v in ((hid, v_termo), (otro, v_otro)):
        db.execute(
            "INSERT INTO objeto_embedding (objeto_tipo, objeto_id, sede_id, categoria_id, modelo, "
            "texto_normalizado, vector) VALUES ('hallado', %s, 1, 7, 'prueba', 'termo', %s::vector)",
            (oid, str(v)),
        )
    consulta = [0.9, 0.1] + [0.0] * 1022
    primero = db.execute(
        "SELECT objeto_id FROM objeto_embedding WHERE sede_id=1 AND categoria_id=7 AND modelo='prueba' "
        "ORDER BY vector <=> %s::vector LIMIT 1",
        (str(consulta),),
    ).fetchone()[0]
    assert primero == hid
