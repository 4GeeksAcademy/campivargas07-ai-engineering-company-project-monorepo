"""test_locales.py — CRUD de locales + regla de negocio moneda-país."""
from __future__ import annotations


def test_crud_local_completo(client, auth_headers):
    """Crear → listar → actualizar → borrar."""
    payload = {"nombre": "Local Test CRUD", "ciudad": "Cali", "pais": "CO", "direccion": "Calle 5 #1-2"}
    r = client.post("/api/v1/locales", headers=auth_headers, json=payload)
    assert r.status_code == 201, r.text
    local = r.json()
    assert local["moneda"] == "COP"  # regla: CO → COP
    local_id = local["id"]

    r = client.get(f"/api/v1/locales/{local_id}")
    assert r.status_code == 200

    # Cambiar país a US → moneda se recalcula a USD
    r = client.put(f"/api/v1/locales/{local_id}", headers=auth_headers, json={"pais": "US"})
    assert r.status_code == 200
    assert r.json()["moneda"] == "USD"

    r = client.delete(f"/api/v1/locales/{local_id}", headers=auth_headers)
    assert r.status_code == 204

    r = client.get(f"/api/v1/locales/{local_id}")
    assert r.status_code == 404


def test_local_pais_invalido_422(client, auth_headers):
    r = client.post(
        "/api/v1/locales", headers=auth_headers,
        json={"nombre": "Local Invalido", "ciudad": "Paris", "pais": "FR"},
    )
    assert r.status_code == 422  # rechazado por validador de Pydantic


def test_locales_sin_token_401(client):
    r = client.post("/api/v1/locales", json={"nombre": "X", "ciudad": "Y", "pais": "CO"})
    assert r.status_code == 401