"""Authenticated password-change API tests."""

from fastapi.testclient import TestClient
from tinydb import Query, TinyDB

from app.domains.auth.service import verify_password


def test_change_password_success(
    client: TestClient, auth_headers: dict[str, str], test_db: TinyDB,
) -> None:
    response = client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "NewPass456"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    user = test_db.table("users").get(Query().email == "usuario.prueba@brasaland.com")
    assert verify_password("NewPass456", user["hashed_password"])


def test_change_password_rejects_wrong_same_and_weak_passwords(
    client: TestClient, auth_headers: dict[str, str],
) -> None:
    wrong = client.post(
        "/auth/change-password",
        json={"current_password": "wrong", "new_password": "NewPass456"},
        headers=auth_headers,
    )
    same = client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "password123"},
        headers=auth_headers,
    )
    weak = client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "lowercase1"},
        headers=auth_headers,
    )

    assert wrong.status_code == 400
    assert same.status_code == 400
    assert weak.status_code == 422


def test_change_password_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/auth/change-password",
        json={"current_password": "password123", "new_password": "NewPass456"},
    )
    assert response.status_code == 401
