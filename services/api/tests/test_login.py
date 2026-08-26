"""
test_login.py — Tests for user login (POST /auth/login)

Verifies correct authentication, incorrect password, nonexistent email,
inactive accounts, corrupted stored hashes, and generic error messages.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from tinydb import TinyDB

from app.domains.auth.service import decode_access_token


def test_login_success(client: TestClient, create_test_user) -> None:
    """Valid credentials return a JWT access token with Bearer type."""
    create_test_user(
        email="felipe.operaciones@brasaland.com",
        password="PasswordFelipe2026!",
        role="manager",
    )

    payload = {
        "email": "felipe.operaciones@brasaland.com",
        "password": "PasswordFelipe2026!",
    }
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify decoded token claims
    token_payload = decode_access_token(data["access_token"])
    assert token_payload is not None
    assert token_payload["role"] == "manager"


def test_login_incorrect_password(client: TestClient, create_test_user) -> None:
    """Incorrect password returns 401 Unauthorized with WWW-Authenticate header."""
    create_test_user(
        email="lucia.compras@brasaland.com",
        password="PasswordCorrecta123",
    )

    payload = {
        "email": "lucia.compras@brasaland.com",
        "password": "PasswordIncorrecta999",
    }
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    assert "Bearer" in response.headers.get("www-authenticate", "")


def test_login_nonexistent_email_returns_identical_401(client: TestClient) -> None:
    """Non-existent email returns the same 401 error message, preventing user enumeration."""
    payload = {
        "email": "no.existe@brasaland.com",
        "password": "AlgunaPassword123",
    }
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_inactive_user_returns_403(
    client: TestClient, create_test_user
) -> None:
    """Inactive accounts with valid credentials return 403 Forbidden."""
    create_test_user(
        email="inactivo@brasaland.com",
        password="Password123!",
        is_active=False,
    )

    payload = {
        "email": "inactivo@brasaland.com",
        "password": "Password123!",
    }
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


def test_login_corrupted_hash_in_db_returns_401_safely(
    client: TestClient, test_db: TinyDB
) -> None:
    """A corrupted bcrypt hash in the database is handled gracefully and returns 401."""
    users_tbl = test_db.table("users")
    doc_id = users_tbl.insert(
        {
            "email": "corrupto@brasaland.com",
            "hashed_password": "not_a_valid_hash_format_$$$",
            "role": "user",
            "is_active": True,
            "created_at": "2026-08-01T00:00:00+00:00",
        }
    )
    users_tbl.update({"doc_id": doc_id}, doc_ids=[doc_id])

    payload = {
        "email": "corrupto@brasaland.com",
        "password": "Password123!",
    }
    response = client.post("/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"


def test_login_missing_required_fields_returns_422(client: TestClient) -> None:
    """Missing email or password in request body returns 422 Unprocessable Entity."""
    response_no_pass = client.post("/auth/login", json={"email": "test@test.com"})
    assert response_no_pass.status_code == 422

    response_no_email = client.post("/auth/login", json={"password": "pwd"})
    assert response_no_email.status_code == 422

