from pathlib import Path
import sys
import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from app.main import app
from app.database import users_table, profiles_table

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    # Cleanup test users after each test if needed


def test_healthcheck():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_user_registration_and_login_flow():
    test_email = f"admin_test_{users_table.__len__() + 1}@brasaland.com"
    test_password = "SecurePassword123!"

    # 1. Register user with role='admin'
    reg_response = client.post(
        "/users",
        json={
            "email": test_email,
            "password": test_password,
            "role": "admin",
            "name": "Admin Tester",
            "phone": "+57 300 0000000",
            "address": "Calle 10 # 40-20, Medellín",
        },
    )
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["email"] == test_email
    assert user_data["role"] == "admin"
    assert user_data["is_active"] is True

    # 2. Login to get JWT access token
    login_response = client.post(
        "/auth/login",
        json={
            "email": test_email,
            "password": test_password,
        },
    )
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    access_token = token_data["access_token"]

    # 3. Get /auth/me with Bearer token
    me_response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    me_data = me_response.json()
    assert me_data["user"]["email"] == test_email
    assert me_data["user"]["role"] == "admin"
    assert me_data["profile"]["name"] == "Admin Tester"
    assert me_data["profile"]["phone"] == "+57 300 0000000"


def test_registration_with_default_role():
    test_email = f"default_role_{users_table.__len__() + 1}@brasaland.com"
    test_password = "SecurePassword123!"

    reg_response = client.post(
        "/users",
        json={
            "email": test_email,
            "password": test_password,
        },
    )
    assert reg_response.status_code == 201
    user_data = reg_response.json()
    assert user_data["role"] == "admin"

