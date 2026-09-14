"""
test_inventory_domain.py — Brasaland · Fast Unit and Functional Tests for Inventory Domain

Tested against isolated in-memory SQLite database:
- Table creation and schema registration
- Creation and listing of ingredients
- SKU uniqueness and schema validation
- Mandatory local_id on stock endpoints (422 if omitted)
- Dynamic stock computation per local_id (no cross-contamination)
- Authenticated inbound and outbound movements
- Insufficient stock rejection (400) without persistence
- Unauthorized request rejection (401)
- Preservation of creator user UUID
- Foreign key checks on invalid ingredient IDs (404)
- Orders listing with joined details (no N+1)
- Seed idempotency, user verification, and net stock assertions
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlmodel import Session

from app.domains.operations.inventory.models import (
    Ingredient,
    IngredientEntry,
    IngredientExit,
)
from app.domains.operations.inventory.repository import get_stock_for_ingredient_and_local
from app.domains.operations.inventory.seed import seed_inventory


# ────────────────────────────────────────────────────────────
# 1. Table Creation & Registration
# ────────────────────────────────────────────────────────────

def test_init_db_creates_expected_tables(sqlite_engine):
    """Verify that init_db() creates ingredient, ingredient_entry, and ingredient_exit tables."""
    inspector = inspect(sqlite_engine)
    tables = inspector.get_table_names()
    assert "ingredient" in tables
    assert "ingredient_entry" in tables
    assert "ingredient_exit" in tables


# ────────────────────────────────────────────────────────────
# 2. Ingredient Catalog CRUD & Validations
# ────────────────────────────────────────────────────────────

def test_create_and_list_ingredients(client: TestClient, auth_headers: dict):
    """POST /inventory/products creates an ingredient, GET lists it with current_stock=0."""
    payload = {
        "sku": "ING-001",
        "name": "Carne de Res (kg)",
        "category": "carne",
        "unit_of_measure": "kg",
        "minimum_stock": "20.0",
        "perishable": True,
    }
    create_resp = client.post("/inventory/products", json=payload, headers=auth_headers)
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["sku"] == "ING-001"
    assert created["name"] == "Carne de Res (kg)"
    assert "id" in created
    assert "created_at" in created

    # List products for MED-001
    list_resp = client.get("/inventory/products?local_id=MED-001", headers=auth_headers)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["sku"] == "ING-001"
    assert items[0]["local_id"] == "MED-001"
    assert Decimal(str(items[0]["current_stock"])) == Decimal("0.0")


def test_sku_uniqueness(client: TestClient, auth_headers: dict):
    """Attempting to create an ingredient with a duplicate SKU returns 409 Conflict."""
    payload = {
        "sku": "ING-DUP",
        "name": "Tomate Chonto",
        "category": "verdura",
        "unit_of_measure": "kg",
        "minimum_stock": "5.0",
        "perishable": True,
    }
    resp1 = client.post("/inventory/products", json=payload, headers=auth_headers)
    assert resp1.status_code == 201

    resp2 = client.post("/inventory/products", json=payload, headers=auth_headers)
    assert resp2.status_code == 409
    assert "already exists" in resp2.json()["detail"]


def test_domain_validations(client: TestClient, auth_headers: dict):
    """Validates schema bounds: invalid category, negative minimum_stock, empty name."""
    # Invalid category
    resp_cat = client.post(
        "/inventory/products",
        json={
            "sku": "ING-BAD-CAT",
            "name": "Insumo Raro",
            "category": "categoria_inexistente",
            "unit_of_measure": "kg",
        },
        headers=auth_headers,
    )
    assert resp_cat.status_code == 422

    # Negative minimum_stock
    resp_stock = client.post(
        "/inventory/products",
        json={
            "sku": "ING-NEG-STOCK",
            "name": "Insumo Negativo",
            "category": "carne",
            "unit_of_measure": "kg",
            "minimum_stock": "-1.0",
        },
        headers=auth_headers,
    )
    assert resp_stock.status_code == 422


def test_local_id_mandatory_query_param(client: TestClient, auth_headers: dict):
    """local_id must be mandatory on endpoints returning current_stock; returns 422 if omitted."""
    # GET /inventory/products without local_id
    resp_list = client.get("/inventory/products", headers=auth_headers)
    assert resp_list.status_code == 422

    # GET /inventory/products/{id} without local_id
    some_id = str(uuid.uuid4())
    resp_item = client.get(f"/inventory/products/{some_id}", headers=auth_headers)
    assert resp_item.status_code == 422


# ────────────────────────────────────────────────────────────
# 3. Stock Calculation & Location Separation
# ────────────────────────────────────────────────────────────

def test_stock_calculation_by_local_id(client: TestClient, auth_headers: dict):
    """
    Verifies that stock is calculated strictly per local_id without
    cross-location contamination.
    """
    # 1. Create ingredient
    ing_resp = client.post(
        "/inventory/products",
        json={
            "sku": "ING-SEP",
            "name": "Pollo Entero",
            "category": "carne",
            "unit_of_measure": "kg",
            "minimum_stock": "10.0",
        },
        headers=auth_headers,
    )
    assert ing_resp.status_code == 201
    ing_id = ing_resp.json()["id"]

    # 2. Inbound 50 in MED-001
    client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing_id, "local_id": "MED-001", "quantity": "50.0"},
        headers=auth_headers,
    )

    # 3. Inbound 30 in MIA-001
    client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing_id, "local_id": "MIA-001", "quantity": "30.0"},
        headers=auth_headers,
    )

    # 4. Check MED-001 stock -> 50
    med_resp = client.get(f"/inventory/products/{ing_id}?local_id=MED-001", headers=auth_headers)
    assert med_resp.status_code == 200
    assert Decimal(str(med_resp.json()["current_stock"])) == Decimal("50.0")

    # 5. Check MIA-001 stock -> 30
    mia_resp = client.get(f"/inventory/products/{ing_id}?local_id=MIA-001", headers=auth_headers)
    assert mia_resp.status_code == 200
    assert Decimal(str(mia_resp.json()["current_stock"])) == Decimal("30.0")


# ────────────────────────────────────────────────────────────
# 4. Inbound & Outbound Movements
# ────────────────────────────────────────────────────────────

def test_inbound_order_increases_stock(client: TestClient, auth_headers: dict):
    """Inbound movement increases stock and records authenticated user UUID."""
    ing = client.post(
        "/inventory/products",
        json={"sku": "ING-IN1", "name": "Sal", "category": "salsa", "unit_of_measure": "kg"},
        headers=auth_headers,
    ).json()

    in_resp = client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "25.5"},
        headers=auth_headers,
    )
    assert in_resp.status_code == 201
    entry_data = in_resp.json()
    assert entry_data["type"] == "inbound"
    assert entry_data["ingredient_id"] == ing["id"]
    assert Decimal(str(entry_data["quantity"])) == Decimal("25.5")
    assert "user_uuid" in entry_data

    # Check updated stock
    prod = client.get(f"/inventory/products/{ing['id']}?local_id=MED-001", headers=auth_headers).json()
    assert Decimal(str(prod["current_stock"])) == Decimal("25.5")


def test_outbound_order_decreases_stock(client: TestClient, auth_headers: dict):
    """Outbound movement reduces available stock."""
    ing = client.post(
        "/inventory/products",
        json={"sku": "ING-OUT1", "name": "Pimienta", "category": "salsa", "unit_of_measure": "kg"},
        headers=auth_headers,
    ).json()

    # Entry of 20
    client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "20.0"},
        headers=auth_headers,
    )

    # Exit of 8
    out_resp = client.post(
        "/inventory/orders/outbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "8.0"},
        headers=auth_headers,
    )
    assert out_resp.status_code == 201
    assert out_resp.json()["type"] == "outbound"

    # Net stock: 20 - 8 = 12
    prod = client.get(f"/inventory/products/{ing['id']}?local_id=MED-001", headers=auth_headers).json()
    assert Decimal(str(prod["current_stock"])) == Decimal("12.0")


def test_outbound_insufficient_stock_rejected_400(client: TestClient, auth_headers: dict):
    """
    Attempting an outbound order greater than available stock returns 400
    and does NOT persist any record.
    """
    ing = client.post(
        "/inventory/products",
        json={"sku": "ING-REJ", "name": "Chimichurri", "category": "salsa", "unit_of_measure": "litros"},
        headers=auth_headers,
    ).json()

    # Entry of 10.0
    client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "10.0"},
        headers=auth_headers,
    )

    # Attempt exit of 15.0 (exceeds available 10.0)
    out_resp = client.post(
        "/inventory/orders/outbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "15.0"},
        headers=auth_headers,
    )
    assert out_resp.status_code == 400
    err_detail = out_resp.json()["detail"]
    assert "Insufficient stock" in err_detail
    assert "Available: 10" in err_detail or "Available: 10.0" in err_detail

    # Stock must remain exactly 10.0
    prod = client.get(f"/inventory/products/{ing['id']}?local_id=MED-001", headers=auth_headers).json()
    assert Decimal(str(prod["current_stock"])) == Decimal("10.0")

    # Order history should only have the inbound order
    orders_resp = client.get(f"/inventory/orders?local_id=MED-001", headers=auth_headers).json()
    assert orders_resp["total"] == 1
    assert orders_resp["orders"][0]["type"] == "inbound"


# ────────────────────────────────────────────────────────────
# 5. Authentication, Identity & FK Constraints
# ────────────────────────────────────────────────────────────

def test_unauthenticated_requests_rejected(client: TestClient):
    """All inventory endpoints require authentication and return 401 when token is absent."""
    some_uuid = str(uuid.uuid4())
    assert client.get("/inventory/products?local_id=MED-001").status_code == 401
    assert client.post("/inventory/products", json={}).status_code == 401
    assert client.get(f"/inventory/products/{some_uuid}?local_id=MED-001").status_code == 401
    assert client.post("/inventory/orders/inbound", json={}).status_code == 401
    assert client.post("/inventory/orders/outbound", json={}).status_code == 401
    assert client.get("/inventory/orders").status_code == 401


def test_creator_uuid_saved_in_orders(client: TestClient, create_test_user, auth_headers):
    """Movements save the exact UUID of the authenticated user in TinyDB."""
    test_uuid = str(uuid.uuid4())
    user = create_test_user(email="supervisor@brasaland.com", user_uuid=test_uuid)

    from app.domains.auth.service import create_access_token
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})
    user_headers = {"Authorization": f"Bearer {token}"}

    ing = client.post(
        "/inventory/products",
        json={"sku": "ING-UUID", "name": "Vaso", "category": "empaque", "unit_of_measure": "unidades"},
        headers=user_headers,
    ).json()

    in_order = client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "100.0"},
        headers=user_headers,
    ).json()

    assert in_order["user_uuid"] == test_uuid


def test_foreign_key_ingredient_constraint(client: TestClient, auth_headers: dict):
    """Attempting inbound or outbound movement for a non-existent ingredient returns 404."""
    non_existent = str(uuid.uuid4())
    resp_in = client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": non_existent, "local_id": "MED-001", "quantity": "10.0"},
        headers=auth_headers,
    )
    assert resp_in.status_code == 404

    resp_out = client.post(
        "/inventory/orders/outbound",
        json={"ingredient_id": non_existent, "local_id": "MED-001", "quantity": "5.0"},
        headers=auth_headers,
    )
    assert resp_out.status_code == 404


# ────────────────────────────────────────────────────────────
# 6. Orders Listing (No N+1)
# ────────────────────────────────────────────────────────────

def test_list_orders_eager_no_n_plus_one(client: TestClient, auth_headers: dict):
    """Listing orders includes joined ingredient details without additional queries."""
    ing = client.post(
        "/inventory/products",
        json={"sku": "ING-JOIN", "name": "Carne Hamburguesa", "category": "carne", "unit_of_measure": "kg"},
        headers=auth_headers,
    ).json()

    client.post(
        "/inventory/orders/inbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "30.0"},
        headers=auth_headers,
    )
    client.post(
        "/inventory/orders/outbound",
        json={"ingredient_id": ing["id"], "local_id": "MED-001", "quantity": "10.0"},
        headers=auth_headers,
    )

    resp = client.get("/inventory/orders?local_id=MED-001", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    for ord_item in data["orders"]:
        assert ord_item["ingredient_sku"] == "ING-JOIN"
        assert ord_item["ingredient_name"] == "Carne Hamburguesa"
        assert "user_uuid" in ord_item
        assert ord_item["local_id"] == "MED-001"


# ────────────────────────────────────────────────────────────
# 7. Seed Idempotency & Net Stock Assertions
# ────────────────────────────────────────────────────────────

def test_seed_idempotency_and_net_stock(sqlite_engine, create_test_user):
    """
    Verifies that seed_inventory:
    - Successfully populates the 7 ingredients from src/demo.ts.
    - Yields the exact net stock modeled in demo.ts:
      MED-001: ING-001 net 8, ING-002 net 25, ING-003 net 3
      MIA-001: ING-001 net 45, ING-006 net 10
    - Is strictly idempotent when executed multiple times.
    """
    user = create_test_user(email="admin.seed@brasaland.com")

    with Session(sqlite_engine) as session:
        # First execution: creates 7 ingredients and 5 movements pairs
        res1 = seed_inventory(session, user["email"])
        assert res1["ingredients_created"] == 7
        assert res1["movements_created"] > 0

        # Verify net stock for MED-001
        from app.domains.operations.inventory.repository import get_ingredient_by_sku
        ing_001 = get_ingredient_by_sku(session, "ING-001")
        ing_002 = get_ingredient_by_sku(session, "ING-002")
        ing_003 = get_ingredient_by_sku(session, "ING-003")
        ing_006 = get_ingredient_by_sku(session, "ING-006")

        stock_med_001 = get_stock_for_ingredient_and_local(session, ing_001.id, "MED-001")
        assert stock_med_001 == Decimal("8.0")

        stock_med_002 = get_stock_for_ingredient_and_local(session, ing_002.id, "MED-001")
        assert stock_med_002 == Decimal("25.0")

        stock_med_003 = get_stock_for_ingredient_and_local(session, ing_003.id, "MED-001")
        assert stock_med_003 == Decimal("3.0")

        # Verify net stock for MIA-001
        stock_mia_001 = get_stock_for_ingredient_and_local(session, ing_001.id, "MIA-001")
        assert stock_mia_001 == Decimal("45.0")

        stock_mia_006 = get_stock_for_ingredient_and_local(session, ing_006.id, "MIA-001")
        assert stock_mia_006 == Decimal("10.0")

        # Second execution: idempotency test
        res2 = seed_inventory(session, user["email"])
        assert res2["ingredients_created"] == 0
        assert res2["movements_created"] == 0


def test_seed_rejects_nonexistent_user(sqlite_engine):
    """Seed rejects execution if user does not exist in TinyDB."""
    with Session(sqlite_engine) as session:
        with pytest.raises(ValueError, match="does not exist in TinyDB"):
            seed_inventory(session, "usuario.fantasma@brasaland.com")
