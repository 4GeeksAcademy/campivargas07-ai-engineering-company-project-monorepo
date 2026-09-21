"""
test_auth_dependency.py — Unit tests for get_current_user FastAPI dependency

Verifies user retrieval from TinyDB, missing sub claim, non-numeric sub,
deleted/nonexistent user, and inactive user status.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, status

from app.domains.auth.dependencies import get_current_user
from app.domains.auth.service import create_access_token


@pytest.mark.anyio
async def test_get_current_user_valid_token(create_test_user) -> None:
    """A valid token for an active user returns the user database record."""
    user = create_test_user(email="valido@brasaland.com", is_active=True)
    token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})

    resolved_user = await get_current_user(token=token)
    assert resolved_user is not None
    assert resolved_user["email"] == "valido@brasaland.com"
    assert resolved_user["doc_id"] == user.doc_id


@pytest.mark.anyio
async def test_get_current_user_missing_sub_claim_raises_401() -> None:
    """A token without 'sub' claim raises HTTP 401 Unauthorized."""
    token = create_access_token(data={"role": "admin"})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.anyio
async def test_get_current_user_non_numeric_sub_raises_401() -> None:
    """A token with a non-integer 'sub' claim raises HTTP 401 Unauthorized."""
    token = create_access_token(data={"sub": "not-an-integer-id", "role": "user"})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.anyio
async def test_get_current_user_nonexistent_user_raises_401() -> None:
    """A token referring to a user doc_id not in TinyDB raises HTTP 401 Unauthorized."""
    token = create_access_token(data={"sub": "999999", "role": "user"})

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.anyio
async def test_get_current_user_inactive_user_raises_403(create_test_user) -> None:
    """A token for an existing user whose is_active is False raises HTTP 403 Forbidden."""
    inactive_user = create_test_user(
        email="inactivo@brasaland.com", is_active=False
    )
    token = create_access_token(
        data={"sub": str(inactive_user.doc_id), "role": inactive_user["role"]}
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Inactive user account"


@pytest.mark.anyio
async def test_get_current_user_invalid_token_raises_401() -> None:
    """An invalid token string raises HTTP 401 Unauthorized."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="invalid.bearer.token")

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.detail == "Could not validate credentials"

