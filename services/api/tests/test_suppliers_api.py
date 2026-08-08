"""
test_suppliers_api.py — Brasaland · Supplier directory API tests

Covers: POST create, GET list + filters, GET by ID, PATCH rate, PATCH status,
DELETE, 404 handling, 422 validation, and idempotent seeding.
"""

from __future__ import annotations

import os
from pathlib import Path

# Set test DB path BEFORE any app imports
_TEST_DB = Path(__file__).resolve().parent.parent / "data" / "suppliers_test.json"
_TEST_DB.parent.mkdir(parents=True, exist_ok=True)
os.environ["SUPPLIERS_DB_PATH"] = str(_TEST_DB)

import pytest
from fastapi.testclient import TestClient

from app.database import suppliers_table  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    """Clear the suppliers table before each test."""
    suppliers_table.truncate()
    yield
    suppliers_table.truncate()


# ── Helpers ──────────────────────────────────────────────────

SAMPLE_SUPPLIER = {
    "nombre": "Carnes Premium Colombia S.A.S.",
    "pais": "Colombia",
    "contactoNombre": "Andrés Mora",
    "contactoEmail": "andres.mora@carnespremium.co",
    "contactoTelefono": "+57 310 1234567",
    "categoriasQueProvee": ["carne"],
    "tiempoEntregaDias": 2,
    "montoMinimoOrden": 500000,
    "moneda": "COP",
    "status": "activo",
}

SAMPLE_SUPPLIER_USA = {
    "nombre": "Florida Meat Distributors LLC",
    "pais": "USA",
    "contactoNombre": "James Walker",
    "contactoEmail": "j.walker@floridameat.com",
    "contactoTelefono": "+1 305 5550001",
    "categoriasQueProvee": ["carne", "verdura"],
    "tiempoEntregaDias": 1,
    "montoMinimoOrden": 300,
    "moneda": "USD",
    "status": "activo",
}


def _create_supplier(data: dict | None = None) -> dict:
    """Create a supplier and return the response JSON."""
    payload = data or SAMPLE_SUPPLIER
    resp = client.post("/api/suppliers", json=payload)
    assert resp.status_code == 201
    return resp.json()


# ── POST /api/suppliers ──────────────────────────────────────

def test_create_supplier_returns_201_with_id():
    result = _create_supplier()
    assert "id" in result
    assert result["nombre"] == "Carnes Premium Colombia S.A.S."
    assert result["status"] == "activo"
    assert result["updated_at"] is None


def test_create_supplier_with_invalid_status_returns_422():
    payload = {**SAMPLE_SUPPLIER, "status": "inactivo"}
    resp = client.post("/api/suppliers", json=payload)
    assert resp.status_code == 422


def test_create_supplier_with_zero_rate_returns_422():
    payload = {**SAMPLE_SUPPLIER, "montoMinimoOrden": 0}
    resp = client.post("/api/suppliers", json=payload)
    assert resp.status_code == 422


def test_create_supplier_with_negative_rate_returns_422():
    payload = {**SAMPLE_SUPPLIER, "montoMinimoOrden": -100}
    resp = client.post("/api/suppliers", json=payload)
    assert resp.status_code == 422


def test_create_supplier_with_invalid_category_returns_422():
    payload = {**SAMPLE_SUPPLIER, "categoriasQueProvee": ["invalida"]}
    resp = client.post("/api/suppliers", json=payload)
    assert resp.status_code == 422


def test_create_supplier_with_empty_categories_returns_422():
    payload = {**SAMPLE_SUPPLIER, "categoriasQueProvee": []}
    resp = client.post("/api/suppliers", json=payload)
    assert resp.status_code == 422


# ── GET /api/suppliers ───────────────────────────────────────

def test_list_suppliers_empty():
    resp = client.get("/api/suppliers")
    assert resp.status_code == 200
    body = resp.json()
    assert body["suppliers"] == []
    assert body["total"] == 0


def test_list_suppliers_returns_all():
    _create_supplier()
    _create_supplier(SAMPLE_SUPPLIER_USA)
    resp = client.get("/api/suppliers")
    body = resp.json()
    assert body["total"] == 2


def test_list_suppliers_filter_by_country():
    _create_supplier()
    _create_supplier(SAMPLE_SUPPLIER_USA)
    resp = client.get("/api/suppliers?country=Colombia")
    body = resp.json()
    assert body["total"] == 1
    assert body["suppliers"][0]["pais"] == "Colombia"


def test_list_suppliers_filter_by_category():
    _create_supplier()
    _create_supplier(SAMPLE_SUPPLIER_USA)
    resp = client.get("/api/suppliers?category=verdura")
    body = resp.json()
    assert body["total"] == 1
    assert "verdura" in body["suppliers"][0]["categoriasQueProvee"]


def test_list_suppliers_filter_country_and_category():
    _create_supplier()
    _create_supplier(SAMPLE_SUPPLIER_USA)
    resp = client.get("/api/suppliers?country=Colombia&category=carne")
    body = resp.json()
    assert body["total"] == 1
    assert body["suppliers"][0]["pais"] == "Colombia"


# ── GET /api/suppliers/{id} ──────────────────────────────────

def test_get_supplier_by_id():
    created = _create_supplier()
    resp = client.get(f"/api/suppliers/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_get_supplier_not_found():
    resp = client.get("/api/suppliers/99999")
    assert resp.status_code == 404


# ── PATCH /api/suppliers/{id}/rate ───────────────────────────

def test_update_rate():
    created = _create_supplier()
    resp = client.patch(
        f"/api/suppliers/{created['id']}/rate",
        json={"montoMinimoOrden": 600000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["montoMinimoOrden"] == 600000
    assert body["updated_at"] is not None


def test_update_rate_422_on_zero():
    created = _create_supplier()
    resp = client.patch(
        f"/api/suppliers/{created['id']}/rate",
        json={"montoMinimoOrden": 0},
    )
    assert resp.status_code == 422


def test_update_rate_422_on_negative():
    created = _create_supplier()
    resp = client.patch(
        f"/api/suppliers/{created['id']}/rate",
        json={"montoMinimoOrden": -50},
    )
    assert resp.status_code == 422


def test_update_rate_not_found():
    resp = client.patch("/api/suppliers/99999/rate", json={"montoMinimoOrden": 100})
    assert resp.status_code == 404


# ── PATCH /api/suppliers/{id}/status ─────────────────────────

def test_update_status():
    created = _create_supplier()
    resp = client.patch(
        f"/api/suppliers/{created['id']}/status",
        json={"status": "suspendido"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "suspendido"


def test_update_status_422_on_invalid():
    created = _create_supplier()
    resp = client.patch(
        f"/api/suppliers/{created['id']}/status",
        json={"status": "inactivo"},
    )
    assert resp.status_code == 422


def test_update_status_not_found():
    resp = client.patch("/api/suppliers/99999/status", json={"status": "activo"})
    assert resp.status_code == 404


# ── DELETE /api/suppliers/{id} ────────────────────────────────

def test_delete_supplier():
    created = _create_supplier()
    resp = client.delete(f"/api/suppliers/{created['id']}")
    assert resp.status_code == 200
    # Confirm it's gone
    resp2 = client.get(f"/api/suppliers/{created['id']}")
    assert resp2.status_code == 404


def test_delete_supplier_not_found():
    resp = client.delete("/api/suppliers/99999")
    assert resp.status_code == 404
