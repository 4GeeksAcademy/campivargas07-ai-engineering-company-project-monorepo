"""
test_me.py — Tests for current authenticated user endpoint (GET /auth/me)

Verifies user profile retrieval, users without profile, expired tokens,
tampered tokens, missing/invalid sub claims, deleted users, and inactive status.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.domains.auth.service import create_access_token


def test_get_me_with_linked_profile(client: TestClient, create_test_user) -> None:
    """Authenticated user with a linked profile receives both user and profile details."""
    user = create_test_user(
        email="mariana.ceo@brasaland.com",
        role="admin",
        name="Mariana Restrepo",
        phone="+57 311 000 1122",
        address="Cra 11 # 93-50, Bogotá",
    )
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user"]["id"] == str(user.doc_id)
    assert data["user"]["email"] == "mariana.ceo@brasaland.com"
    assert data["user"]["role"] == "admin"
    assert data["user"]["is_active"] is True

    assert data["profile"] is not None
    assert data["profile"]["user_id"] == str(user.doc_id)
    assert data["profile"]["name"] == "Mariana Restrepo"
    assert data["profile"]["phone"] == "+57 311 000 1122"
    assert data["profile"]["address"] == "Cra 11 # 93-50, Bogotá"


def test_get_me_without_profile(client: TestClient, create_test_user) -> None:
    """Authenticated user without a profile receives user details and profile=None."""
    user = create_test_user(
        email="sin.perfil@brasaland.com",
        name=None,
        phone=None,
        address=None,
    )
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()

    assert data["user"]["email"] == "sin.perfil@brasaland.com"
    assert data["profile"] is None


def test_get_me_unauthenticated_returns_401(client: TestClient) -> None:
    """Calling /auth/me without an Authorization header returns 401 Unauthorized."""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_get_me_expired_token_returns_401(
    client: TestClient, create_test_user
) -> None:
    """Calling /auth/me with an expired token returns 401 Unauthorized."""
    user = create_test_user()
    token = create_access_token(
        data={"sub": str(user.doc_id), "role": user["role"]},
        expires_delta=timedelta(minutes=-5),
    )

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_me_tampered_token_returns_401(
    client: TestClient, create_test_user
) -> None:
    """Calling /auth/me with a modified/tampered token returns 401 Unauthorized."""
    user = create_test_user()
    token = create_access_token(
        data={"sub": str(user.doc_id), "role": user["role"]}
    )
    tampered_token = token + "tampered_signature"

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tampered_token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_me_missing_sub_claim_returns_401(client: TestClient) -> None:
    """Token missing the 'sub' claim returns 401."""
    token = create_access_token(data={"role": "user"})

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_me_non_numeric_sub_returns_401(client: TestClient) -> None:
    """Token with non-numeric 'sub' claim returns 401."""
    token = create_access_token(data={"sub": "uuid-string-abc", "role": "user"})

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_me_deleted_user_returns_401(client: TestClient) -> None:
    """Token referencing a deleted / non-existent user returns 401."""
    token = create_access_token(data={"sub": "99999", "role": "user"})

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


def test_get_me_inactive_user_returns_403(
    client: TestClient, create_test_user
) -> None:
    """Token for an inactive user returns 403 Forbidden."""
    user = create_test_user(
        email="bloqueado@brasaland.com", is_active=False
    )
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})

    response = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"

