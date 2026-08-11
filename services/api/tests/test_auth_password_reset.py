"""
test_auth_password_reset.py — Brasaland · Password Reset Flow Tests

Tests for POST /auth/forgot-password and POST /auth/reset-password endpoints.
"""

from pathlib import Path
import sys
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

from app.main import app
from app.database import password_resets_table, users_table
from app.domains.auth.email_service import EmailDeliveryResult
from app.domains.auth.service import hash_password


client = TestClient(app)

# Test data
TEST_EMAIL = "test_password_reset@brasaland.com"
TEST_PASSWORD = "OldPass123"
TEST_USER_ID = None


def get_test_user_id() -> int:
    """Return the current test user id from TinyDB."""
    from tinydb import Query

    _Q = Query()
    user = users_table.get(_Q.email == TEST_EMAIL)
    assert user is not None
    return user.doc_id


def setup_function():
    """Create a test user before each test."""
    global TEST_USER_ID
    # Clean up previous test data
    from tinydb import Query
    _Q = Query()
    users_table.remove(_Q.email == TEST_EMAIL)
    if TEST_USER_ID:
        password_resets_table.remove(_Q.user_id == str(TEST_USER_ID))

    # Create test user
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
    if TEST_USER_ID:
        password_resets_table.remove(_Q.user_id == str(TEST_USER_ID))


class TestForgotPassword:
    """Tests for POST /auth/forgot-password"""

    def setup_method(self):
        setup_function()

    def teardown_method(self):
        teardown_function()

    def test_forgot_password_returns_success_message(self):
        """Should always return same message regardless of email existence."""
        response = client.post(
            "/auth/forgot-password",
            json={"email": TEST_EMAIL},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Si el email existe, recibirás un enlace de recuperación."

    def test_forgot_password_nonexistent_email_returns_same_message(self):
        """Should return same message for non-existent email (prevent enumeration)."""
        response = client.post(
            "/auth/forgot-password",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["detail"] == "Si el email existe, recibirás un enlace de recuperación."

    def test_forgot_password_creates_token_record(self):
        """Should create a token record in TinyDB for existing user."""
        response = client.post(
            "/auth/forgot-password",
            json={"email": TEST_EMAIL},
        )
        assert response.status_code == 200
        assert response.json()["debug_reset_link"].startswith("http://localhost:3000/reset-password?token=")

        # Verify token record was created
        from tinydb import Query
        _Q = Query()
        token_records = password_resets_table.search(
            (_Q.user_id == str(get_test_user_id())) & (_Q.purpose == "password_reset")
        )
        assert len(token_records) == 1
        assert token_records[0]["used"] is False

    def test_forgot_password_invalidates_previous_tokens(self):
        """Should invalidate previous tokens when new one is requested."""
        # First request
        client.post(
            "/auth/forgot-password",
            json={"email": TEST_EMAIL},
        )

        # Second request
        client.post(
            "/auth/forgot-password",
            json={"email": TEST_EMAIL},
        )

        # Verify only one active token exists
        from tinydb import Query
        _Q = Query()
        active_tokens = password_resets_table.search(
            (_Q.user_id == str(get_test_user_id())) & (_Q.purpose == "password_reset") & (_Q.used == False)
        )
        assert len(active_tokens) == 1

    def test_forgot_password_invalid_email_format(self):
        """Should reject invalid email format."""
        response = client.post(
            "/auth/forgot-password",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422  # Validation error

    def test_forgot_password_sends_email(self):
        """Should call send_reset_email in background."""
        with patch(
            "app.domains.auth.router.send_reset_email",
            new=AsyncMock(return_value=EmailDeliveryResult(
                sent=True,
                reset_link="http://localhost:3000/reset-password?token=test-token",
                provider_status=200,
            )),
        ) as mock_send:
            response = client.post(
                "/auth/forgot-password",
                json={"email": TEST_EMAIL},
            )
            assert response.status_code == 200
            mock_send.assert_called_once()


class TestResetPassword:
    """Tests for POST /auth/reset-password"""

    def setup_method(self):
        setup_function()

    def teardown_method(self):
        teardown_function()

    def _get_reset_token(self) -> str:
        """Helper to get a valid reset token."""
        from app.domains.auth.service import create_reset_token, decode_reset_token
        user_id = str(get_test_user_id())
        token = create_reset_token(user_id)
        payload = decode_reset_token(token)
        jti = payload.get("jti", "")
        expires_at = payload.get("exp", 0)

        from datetime import datetime, timezone
        password_resets_table.insert({
            "user_id": user_id,
            "jti": jti,
            "purpose": "password_reset",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
            "used": False,
        })
        return token

    def test_reset_password_success(self):
        """Should successfully reset password with valid token."""
        token = self._get_reset_token()
        new_password = "NewPass456"

        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": new_password},
        )
        assert response.status_code == 200
        assert "exitosamente" in response.json()["detail"].lower() or "contraseña" in response.json()["detail"].lower()

        # Verify password was updated
        from tinydb import Query
        _Q = Query()
        user = users_table.get(_Q.email == TEST_EMAIL)
        assert user is not None
        assert verify_password(new_password, user["hashed_password"])

    def test_reset_password_invalid_token(self):
        """Should reject invalid token."""
        response = client.post(
            "/auth/reset-password",
            json={"token": "invalid.token.here", "new_password": "NewPass456"},
        )
        assert response.status_code == 400
        assert "inválido" in response.json()["detail"].lower() or "expirado" in response.json()["detail"].lower()

    def test_reset_password_used_token(self):
        """Should reject already used token."""
        token = self._get_reset_token()

        # First use - should succeed
        client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "NewPass456"},
        )

        # Second use - should fail
        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "AnotherPass789"},
        )
        assert response.status_code == 400

    def test_reset_password_weak_password(self):
        """Should reject password that doesn't meet policy."""
        token = self._get_reset_token()

        # Too short
        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "abc"},
        )
        assert response.status_code == 422

    def test_reset_password_no_uppercase(self):
        """Should reject password without uppercase."""
        token = self._get_reset_token()

        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "alllower123"},
        )
        assert response.status_code == 422

    def test_reset_password_no_digit(self):
        """Should reject password without digit."""
        token = self._get_reset_token()

        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "NoDigitHere"},
        )
        assert response.status_code == 422

    def test_reset_password_token_not_in_db(self):
        """Should reject token not found in database."""
        from app.domains.auth.service import create_reset_token
        token = create_reset_token(str(get_test_user_id()))

        response = client.post(
            "/auth/reset-password",
            json={"token": token, "new_password": "NewPass456"},
        )
        assert response.status_code == 400


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Helper to verify password."""
    from app.domains.auth.service import verify_password as _verify
    return _verify(plain_password, hashed_password)
