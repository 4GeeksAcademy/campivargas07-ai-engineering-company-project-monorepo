"""Regression tests for the supplier directory API."""

from __future__ import annotations

from fastapi.testclient import TestClient


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
    **SAMPLE_SUPPLIER,
    "nombre": "Florida Meat Distributors LLC",
    "pais": "USA",
    "contactoNombre": "James Walker",
    "contactoEmail": "j.walker@floridameat.com",
    "contactoTelefono": "+1 305 5550001",
    "categoriasQueProvee": ["carne", "verdura"],
    "tiempoEntregaDias": 1,
    "montoMinimoOrden": 300,
    "moneda": "USD",
}


def create_supplier(
    client: TestClient,
    auth_headers: dict[str, str],
    payload: dict | None = None,
) -> dict:
    response = client.post(
        "/api/suppliers",
        json=payload or SAMPLE_SUPPLIER,
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


def test_list_suppliers_is_public_and_empty(client: TestClient):
    response = client.get("/api/suppliers")
    assert response.status_code == 200
    assert response.json() == {"suppliers": [], "total": 0}


def test_create_supplier_requires_authentication(client: TestClient):
    response = client.post("/api/suppliers", json=SAMPLE_SUPPLIER)
    assert response.status_code == 401


def test_create_and_get_supplier(client: TestClient, auth_headers: dict[str, str]):
    created = create_supplier(client, auth_headers)

    assert created["id"]
    assert created["nombre"] == SAMPLE_SUPPLIER["nombre"]
    assert created["updated_at"] is None

    response = client.get(f"/api/suppliers/{created['id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_list_filters_by_country_and_category(
    client: TestClient,
    auth_headers: dict[str, str],
):
    create_supplier(client, auth_headers)
    create_supplier(client, auth_headers, SAMPLE_SUPPLIER_USA)

    by_country = client.get("/api/suppliers?country=Colombia").json()
    by_category = client.get("/api/suppliers?category=verdura").json()

    assert by_country["total"] == 1
    assert by_country["suppliers"][0]["pais"] == "Colombia"
    assert by_category["total"] == 1
    assert by_category["suppliers"][0]["pais"] == "USA"


def test_create_validates_rate_category_and_status(
    client: TestClient,
    auth_headers: dict[str, str],
):
    invalid_payloads = [
        {**SAMPLE_SUPPLIER, "montoMinimoOrden": 0},
        {**SAMPLE_SUPPLIER, "categoriasQueProvee": []},
        {**SAMPLE_SUPPLIER, "categoriasQueProvee": ["invalida"]},
        {**SAMPLE_SUPPLIER, "status": "inactivo"},
    ]

    for payload in invalid_payloads:
        response = client.post(
            "/api/suppliers",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 422


def test_update_rate_requires_auth_and_sets_timestamp(
    client: TestClient,
    auth_headers: dict[str, str],
):
    created = create_supplier(client, auth_headers)
    path = f"/api/suppliers/{created['id']}/rate"

    assert client.patch(path, json={"montoMinimoOrden": 600000}).status_code == 401

    response = client.patch(
        path,
        json={"montoMinimoOrden": 600000},
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["montoMinimoOrden"] == 600000
    assert response.json()["updated_at"] is not None


def test_update_status_and_delete_supplier(
    client: TestClient,
    auth_headers: dict[str, str],
):
    created = create_supplier(client, auth_headers)
    supplier_path = f"/api/suppliers/{created['id']}"

    status_response = client.patch(
        f"{supplier_path}/status",
        json={"status": "suspendido"},
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "suspendido"

    delete_response = client.delete(supplier_path, headers=auth_headers)
    assert delete_response.status_code == 200
    assert client.get(supplier_path).status_code == 404


def test_unknown_and_non_numeric_ids_return_404(
    client: TestClient,
    auth_headers: dict[str, str],
):
    for supplier_id in ("99999", "not-a-number"):
        assert client.get(f"/api/suppliers/{supplier_id}").status_code == 404
        assert client.patch(
            f"/api/suppliers/{supplier_id}/rate",
            json={"montoMinimoOrden": 100},
            headers=auth_headers,
        ).status_code == 404
        assert client.delete(
            f"/api/suppliers/{supplier_id}",
            headers=auth_headers,
        ).status_code == 404
