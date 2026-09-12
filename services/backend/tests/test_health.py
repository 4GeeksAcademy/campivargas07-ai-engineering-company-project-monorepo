"""test_health.py — Smoke tests básicos de la aplicación."""
from __future__ import annotations


def test_health_status(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "brasaland-backend"
    assert body["environment"] == "brasaland_db"


def test_openapi_lists_api_paths(client):
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/api/v1/ingredientes" in paths
    assert "/api/v1/inventario/alertas" in paths
    assert "/api/v1/recetas" in paths
    # requisito del hito: >= 8 endpoints (contamos operaciones HTTP por ruta)
    operaciones = sum(len(ops) for ops in paths.values())
    assert len(paths) >= 8
    assert operaciones >= 8


def test_recetas_post_requires_auth(client):
    """Escribir en Mongo sin JWT debe devolver 401."""
    r = client.post(
        "/api/v1/recetas",
        json={
            "plato": "Plato Sin Token",
            "categoria": "test",
            "porciones": 1,
            "ingredientes": [{"ingrediente_id": 1, "nombre": "X", "cantidad": 1, "unidad": "kg"}],
            "pasos": [{"orden": 1, "descripcion": "Paso de prueba largo"}],
        },
    )
    assert r.status_code == 401


def test_token_invalid_credentials(client):
    r = client.post("/api/v1/auth/token", data={"username": "nobody@x.com", "password": "wrong"})
    assert r.status_code == 401