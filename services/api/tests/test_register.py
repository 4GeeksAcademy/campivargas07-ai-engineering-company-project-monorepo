"""
test_register.py — Tests for user registration (POST /users)

Verifies successful creation, optional profile linking, duplicate conflict,
password hashing in persistence, validation bounds, and admin role assignment behavior.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tinydb import Query, TinyDB

from app.domains.auth.service import verify_password


def test_register_user_success_with_full_profile(
    client: TestClient, test_db: TinyDB
) -> None:
    """Registering a new user with profile fields creates user and linked profile."""
    payload = {
        "email": "carlos.gerente@brasaland.com",
        "password": "Password123!",
        "role": "manager",
        "name": "Carlos Vargas",
        "phone": "+57 300 987 6543",
        "address": "Carrera 7 # 72-41, Bogotá",
    }

    response = client.post("/users", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["email"] == "carlos.gerente@brasaland.com"
    assert data["role"] == "manager"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data

    # Verify TinyDB persistence
    users_tbl = test_db.table("users")
    user_doc = users_tbl.get(doc_id=int(data["id"]))
    assert user_doc is not None
    assert user_doc["email"] == "carlos.gerente@brasaland.com"
    # Password must be stored as a hash, not plain text
    assert user_doc["hashed_password"] != "Password123!"
    assert verify_password("Password123!", user_doc["hashed_password"]) is True

    # Verify linked profile persistence
    profiles_tbl = test_db.table("profiles")
    profile_doc = profiles_tbl.get(Query().user_id == data["id"])
    assert profile_doc is not None
    assert profile_doc["name"] == "Carlos Vargas"
    assert profile_doc["phone"] == "+57 300 987 6543"
    assert profile_doc["address"] == "Carrera 7 # 72-41, Bogotá"


def test_register_user_success_with_empty_optional_fields(
    client: TestClient, test_db: TinyDB
) -> None:
    """Registering without profile fields creates only user and no profile record."""
    payload = {
        "email": "solo.usuario@brasaland.com",
        "password": "Minimo6Chars",
    }

    response = client.post("/users", json=payload)
    assert response.status_code == 201
    data = response.json()

    assert data["email"] == "solo.usuario@brasaland.com"
    assert data["role"] == "user"  # Default role

    profiles_tbl = test_db.table("profiles")
    profile_doc = profiles_tbl.get(Query().user_id == data["id"])
    assert profile_doc is None


def test_register_duplicate_email_returns_409_conflict(
    client: TestClient, create_test_user
) -> None:
    """Registering with an already existing email returns 409 Conflict."""
    create_test_user(email="duplicado@brasaland.com")

    payload = {
        "email": "duplicado@brasaland.com",
        "password": "NuevaPassword123",
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_register_password_too_short_returns_422(client: TestClient) -> None:
    """Passwords shorter than 6 characters fail schema validation with 422."""
    payload = {
        "email": "corto@brasaland.com",
        "password": "12345",  # 5 chars
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 422


def test_register_public_admin_role_assignment(client: TestClient) -> None:
    """
    Documents and validates current behavior:
    The public registration endpoint accepts role='admin' in payload.
    """
    payload = {
        "email": "admin.solicitado@brasaland.com",
        "password": "AdminPassword123",
        "role": "admin",
    }
    response = client.post("/users", json=payload)
    assert response.status_code == 201
    assert response.json()["role"] == "admin"

