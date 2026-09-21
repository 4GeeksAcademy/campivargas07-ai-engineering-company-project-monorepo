"""test_recetas_mongo.py — Documentos anidados en MongoDB (doble BD)."""
from __future__ import annotations

import pytest

pytest.importorskip("pymongo")


def _payload_receta(plato: str) -> dict:
    return {
        "plato": plato,
        "categoria": "test",
        "porciones": 2,
        "ingredientes": [
            {"ingrediente_id": 1, "nombre": "Ingrediente SQL", "cantidad": 0.5, "unidad": "kg"},
        ],
        "pasos": [
            {"orden": 1, "descripcion": "Paso uno de la receta de prueba", "duracion_min": 5},
            {"orden": 2, "descripcion": "Paso dos: emplatar y servir caliente", "duracion_min": 3},
        ],
        "tags": ["pytest"],
    }


def test_post_receta_crea_documento_anidado(client, auth_headers):
    """POST /recetas → 201 con _id; el documento guarda ingredientes y pasos anidados."""
    r = client.post("/api/v1/recetas", headers=auth_headers, json=_payload_receta("Receta Test Anidada"))
    assert r.status_code == 201, r.text
    doc = r.json()
    rid = doc["_id"]
    assert rid  # ObjectId serializado
    assert len(doc["ingredientes"]) == 1
    assert doc["ingredientes"][0]["ingrediente_id"] == 1  # referencia a SQL
    assert len(doc["pasos"]) == 2

    # GET por id
    r = client.get(f"/api/v1/recetas/{rid}")
    assert r.status_code == 200
    assert r.json()["plato"] == "Receta Test Anidada"


def test_buscar_recetas_case_insensitive(client, auth_headers):
    client.post("/api/v1/recetas", headers=auth_headers, json=_payload_receta("Ajiaco Santafereño"))
    r = client.get("/api/v1/recetas/buscar", params={"plato": "AJIACO"})
    assert r.status_code == 200
    assert any(d["plato"] == "Ajiaco Santafereño" for d in r.json())


def test_receta_inexistente_404_y_id_invalido_400(client):
    r = client.get("/api/v1/recetas/000000000000000000000000")
    assert r.status_code == 404
    r = client.get("/api/v1/recetas/no-es-un-objectid")
    assert r.status_code == 400


def test_auditoria_registra_operaciones(client, auth_headers):
    """Toda escritura deja log en auditoria_logs (misma BD Mongo)."""
    r = client.post("/api/v1/recetas", headers=auth_headers, json=_payload_receta("Receta Auditada"))
    rid = r.json()["_id"]

    r = client.get("/api/v1/auditoria", headers=auth_headers)
    assert r.status_code == 200
    logs = [l for l in r.json() if l["entidad_id"] == rid]
    assert len(logs) >= 1
    assert logs[0]["accion"] == "crear"
    assert logs[0]["created_at"]  # timestamp ISO derivado del ObjectId

    # Limpieza del documento de prueba
    from app.mongo import get_auditoria_collection, get_recetas_collection
    get_recetas_collection().delete_one({"plato": "Receta Auditada"})
    get_auditoria_collection().delete_many({"entidad_id": rid})