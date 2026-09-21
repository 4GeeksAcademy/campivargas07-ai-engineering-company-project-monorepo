"""
dependencies.py — Brasaland · FastAPI dependency for current user authentication
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.database import users_table

from .service import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """
    Dependency that:
    1. Extracts the Bearer token from the Authorization header.
    2. Decodes and validates the JWT.
    3. Looks up the user in TinyDB by the 'sub' claim (user doc_id).
    4. Ensures the user document contains a stable 'uuid'.
    5. Returns the user document or raises 401/403.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_doc = users_table.get(doc_id=int(user_id))
    except (ValueError, TypeError):
        raise credentials_exception

    if user_doc is None:
        raise credentials_exception

    if not user_doc.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    # Defensive fallback for existing/fixture records without uuid
    if "uuid" not in user_doc:
        stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"brasaland-user-{user_doc.doc_id}"))
        users_table.update({"uuid": stable_uuid}, doc_ids=[user_doc.doc_id])
        user_doc["uuid"] = stable_uuid

    return user_doc
