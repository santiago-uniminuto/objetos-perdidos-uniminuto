from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_salud_responde_ok():
    r = client.get("/api/v1/salud")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"


def test_dependencias_caidas_responden_503(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://x:x@127.0.0.1:1/x")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:1/0")
    from app.config import get_settings

    get_settings.cache_clear()
    r = client.get("/api/v1/salud/dependencias")
    get_settings.cache_clear()

    assert r.status_code == 503
    cuerpo = r.json()
    assert cuerpo["postgres"]["estado"] == "error"
    assert cuerpo["redis"]["estado"] == "error"
    # Nunca se filtran cadenas de conexión en la respuesta
    assert "postgresql://" not in r.text


def test_openapi_publicado():
    r = client.get("/api/openapi.json")
    assert r.status_code == 200
    assert "/api/v1/salud" in r.json()["paths"]
