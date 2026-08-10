"""
service.py — Brasaland · User CRUD + TinyDB persistence
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from tinydb import Query

from app.database import profiles_table, users_table

from .schemas import UserCreate, UserResponse, UserUpdate

_Q = Query()


def _doc_to_response(doc) -> UserResponse:
    """Convert a TinyDB document to a UserResponse."""
    return UserResponse(
        id=str(doc.doc_id),
        email=doc["email"],
        role=doc["role"],
        is_active=doc.get("is_active", True),
        created_at=doc["created_at"],
    )


def create_user(data: UserCreate) -> UserResponse:
    """
    Create a new user with hashed password.
    Also creates a linked Profile if name/phone/address are provided.
    """
    from app.domains.auth.service import hash_password

    existing = users_table.get(_Q.email == data.email)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{data.email}' already exists",
        )

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "email": data.email,
        "hashed_password": hash_password(data.password),
        "role": data.role.value,
        "is_active": True,
        "created_at": now,
    }

    doc_id = users_table.insert(doc)
    users_table.update({"doc_id": doc_id}, doc_ids=[doc_id])

    # Create linked profile if profile fields were provided
    if any(v is not None for v in (data.name, data.phone, data.address)):
        profile_doc = {
            "user_id": str(doc_id),
            "name": data.name,
            "phone": data.phone,
            "address": data.address,
        }
        profile_doc_id = profiles_table.insert(profile_doc)
        profiles_table.update({"doc_id": profile_doc_id}, doc_ids=[profile_doc_id])

    doc = users_table.get(_Q.doc_id == doc_id)
    return _doc_to_response(doc)


def get_all_users() -> list[UserResponse]:
    """List all users."""
    return [_doc_to_response(doc) for doc in users_table.all()]


def get_user_by_id(user_id: str) -> Optional[UserResponse]:
    """Get a user by their TinyDB doc_id."""
    try:
        doc = users_table.get(_Q.doc_id == int(user_id))
    except (ValueError, TypeError):
        return None
    if doc is None:
        return None
    return _doc_to_response(doc)


def update_user(user_id: str, data: UserUpdate) -> Optional[UserResponse]:
    """Update user credentials (email, role)."""
    try:
        doc_id = int(user_id)
    except (ValueError, TypeError):
        return None

    doc = users_table.get(_Q.doc_id == doc_id)
    if doc is None:
        return None

    updates = {}
    if data.email is not None:
        existing = users_table.get(
            (_Q.email == data.email) & (_Q.doc_id != doc_id)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"A user with email '{data.email}' already exists",
            )
        updates["email"] = data.email
    if data.role is not None:
        updates["role"] = data.role.value

    if updates:
        users_table.update(updates, doc_ids=[doc_id])

    doc = users_table.get(_Q.doc_id == doc_id)
    return _doc_to_response(doc)


def delete_user(user_id: str) -> bool:
    """Delete a user and their linked profile."""
    try:
        doc_id = int(user_id)
    except (ValueError, TypeError):
        return False

    doc = users_table.get(_Q.doc_id == doc_id)
    if doc is None:
        return False

    profiles_table.remove(_Q.user_id == str(doc_id))
    users_table.remove(doc_ids=[doc_id])
    return True
