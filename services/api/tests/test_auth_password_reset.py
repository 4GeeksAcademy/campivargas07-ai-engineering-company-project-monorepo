"""Password-reset API tests using the isolated TinyDB fixture."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
from tinydb import Query, TinyDB

from app.domains.auth import router as auth_router
from app.domains.auth.email_service import EmailDeliveryResult
from app.domains.auth.service import hash_password, verify_password


def _create_user(test_db: TinyDB, email: str = "reset@brasaland.com") -> int:
    return test_db.table("users").insert(
        {
            "email": email,
            "hashed_password": hash_password("OldPass123"),
            "role": "user",
            "is_active": True,
            "created_at": "2026-01-01T00:00:00Z",
        }
    )


def _delivery(_email: str, token: str) -> EmailDeliveryResult:
    return EmailDeliveryResult(
        sent=True,
        reset_link=f"http://localhost:3000/reset-password?token={token}",
        provider_status=200,
    )


def test_forgot_password_does_not_reveal_account_existence(
    client: TestClient, test_db: TinyDB, monkeypatch,
) -> None:
    _create_user(test_db)
    send_email = AsyncMock(side_effect=_delivery)
    monkeypatch.setattr(auth_router, "send_reset_email", send_email)

    existing = client.post("/auth/forgot-password", json={"email": "reset@brasaland.com"})
    missing = client.post("/auth/forgot-password", json={"email": "missing@brasaland.com"})

    assert existing.status_code == missing.status_code == 200
    assert existing.json() == missing.json() == {
        "detail": "Si el email existe, recibirás un enlace de recuperación.",
        "debug_reset_link": None,
    }
    send_email.assert_awaited_once()


def test_forgot_password_invalidates_previous_tokens(
    client: TestClient, test_db: TinyDB, monkeypatch,
) -> None:
    user_id = _create_user(test_db)
    monkeypatch.setattr(auth_router, "send_reset_email", AsyncMock(side_effect=_delivery))

    client.post("/auth/forgot-password", json={"email": "reset@brasaland.com"})
    client.post("/auth/forgot-password", json={"email": "reset@brasaland.com"})

    q = Query()
    active = test_db.table("password_resets").search(
        (q.user_id == str(user_id)) & (q.used == False)  # noqa: E712
    )
    assert len(active) == 1


def test_reset_token_is_single_use(
    client: TestClient, test_db: TinyDB, monkeypatch,
) -> None:
    _create_user(test_db)
    monkeypatch.setenv("AUTH_DEBUG_RESET_LINKS", "true")
    monkeypatch.setattr(auth_router, "send_reset_email", AsyncMock(side_effect=_delivery))

    requested = client.post("/auth/forgot-password", json={"email": "reset@brasaland.com"})
    token = requested.json()["debug_reset_link"].split("token=", 1)[1]
    first = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "NewPass456"},
    )
    second = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "AnotherPass789"},
    )

    assert first.status_code == 200
    assert second.status_code == 400
    user = test_db.table("users").get(Query().email == "reset@brasaland.com")
    assert verify_password("NewPass456", user["hashed_password"])


def test_reset_rejects_invalid_token_and_weak_password(
    client: TestClient, test_db: TinyDB, monkeypatch,
) -> None:
    _create_user(test_db)
    invalid = client.post(
        "/auth/reset-password",
        json={"token": "invalid.token", "new_password": "NewPass456"},
    )
    assert invalid.status_code == 400

    monkeypatch.setenv("AUTH_DEBUG_RESET_LINKS", "true")
    monkeypatch.setattr(auth_router, "send_reset_email", AsyncMock(side_effect=_delivery))
    requested = client.post("/auth/forgot-password", json={"email": "reset@brasaland.com"})
    token = requested.json()["debug_reset_link"].split("token=", 1)[1]
    weak = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "lowercase1"},
    )
    assert weak.status_code == 422
