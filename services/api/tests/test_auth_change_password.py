"""
test_auth_change_password.py — Brasaland · Change Password Flow Tests

Tests for POST /auth/change-password endpoint (requires authentication).
"""

from pathlib import Path
import sys

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from app.main import app
from app.database import users_table
from app.domains.auth.service import create_access_token, hash_password


client = TestClient(app)

# Test data
TEST_EMAIL = "test_change_password@brasaland.com"
TEST_PASSWORD = "OldPass123"
TEST_USER_ID = None


def setup_function():
    """Create a test user before each test."""
    global TEST_USER_ID
    from tinydb import Query
    _Q = Query()
    users_table.remove(_Q.email == TEST_EMAIL)

    doc_id = users_table.insert({
        "email": TEST_EMAIL,
        "hashed_password": hash_password(TEST_PASSWORD),
        "role": "user",
        "is_active": True,
        "created_at": "2026-01-01T00:00:00Z",
    })
    TEST_USER_ID = doc_id


def teardown_function():
    """Clean up test data after each test."""
    from tinydb import Query
    _Q = Query()
    users_table.remove(_Q.email == TEST_EMAIL)


def get_auth_headers() -> dict:
    """Helper to get authentication headers."""
    token = create_access_token(data={"sub": str(TEST_USER_ID), "role": "user"})
    return {"Authorization": f"Bearer {token}"}


class TestChangePassword:
    """Tests for POST /auth/change-password"""

    def test_change_password_success(self):
        """Should successfully change password with valid current password."""
        new_password = "NewPass456"
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": new_password,
            },
            headers=get_auth_headers(),
        )
        assert response.status_code == 200
        assert "exitosamente" in response.json()["detail"].lower() or "cambiada" in response.json()["detail"].lower()

        # Verify password was updated
        from tinydb import Query
        _Q = Query()
        user = users_table.get(_Q.email == TEST_EMAIL)
        assert user is not None
        assert verify_password(new_password, user["hashed_password"])

    def test_change_password_wrong_current(self):
        """Should reject wrong current password."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "WrongPass999",
                "new_password": "NewPass456",
            },
            headers=get_auth_headers(),
        )
        assert response.status_code == 400
        assert "actual" in response.json()["detail"].lower() or "incorrecta" in response.json()["detail"].lower()

    def test_change_password_same_password(self):
        """Should reject same password as current."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": TEST_PASSWORD,
            },
            headers=get_auth_headers(),
        )
        assert response.status_code == 400
        assert "diferente" in response.json()["detail"].lower() or "misma" in response.json()["detail"].lower()

    def test_change_password_weak_password(self):
        """Should reject password that doesn't meet policy."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "abc",
            },
            headers=get_auth_headers(),
        )
        assert response.status_code == 400

    def test_change_password_no_uppercase(self):
        """Should reject password without uppercase."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "alllower123",
            },
            headers=get_auth_headers(),
        )
        assert response.status_code == 400

    def test_change_password_no_digit(self):
        """Should reject password without digit."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "NoDigitHere",
            },
            headers=get_auth_headers(),
        )
        assert response.status_code == 400

    def test_change_password_unauthenticated(self):
        """Should reject unauthenticated request."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "NewPass456",
            },
        )
        assert response.status_code == 401

    def test_change_password_invalid_token(self):
        """Should reject invalid JWT token."""
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "NewPass456",
            },
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401

    def test_change_password_chained_operations(self):
        """Should allow multiple password changes."""
        # First change
        response1 = client.post(
            "/api/auth/change-password",
            json={
                "current_password": TEST_PASSWORD,
                "new_password": "SecondPass123",
            },
            headers=get_auth_headers(),
        )
        assert response1.status_code == 200

        # Second change with new current password
        response2 = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "SecondPass123",
                "new_password": "ThirdPass456",
            },
            headers=get_auth_headers(),
        )
        assert response2.status_code == 200

        # Verify final password
        from tinydb import Query
        _Q = Query()
        user = users_table.get(_Q.email == TEST_EMAIL)
        assert user is not None
        assert verify_password("ThirdPass456", user["hashed_password"])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Helper to verify password."""
    from app.domains.auth.service import verify_password as _verify
    return _verify(plain_password, hashed_password)
