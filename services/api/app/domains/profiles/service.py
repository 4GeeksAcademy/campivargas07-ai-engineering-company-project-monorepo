"""
service.py — Brasaland · Profile CRUD + TinyDB persistence
"""

from __future__ import annotations

from typing import Optional

from tinydb import Query

from app.database import profiles_table

from .schemas import ProfileResponse, ProfileUpdate

_Q = Query()


def _doc_to_response(doc) -> ProfileResponse:
    """Convert a TinyDB document to a ProfileResponse."""
    return ProfileResponse(
        id=str(doc.doc_id),
        user_id=doc["user_id"],
        name=doc.get("name"),
        phone=doc.get("phone"),
        address=doc.get("address"),
    )


def get_profile_by_user_id(user_id: str) -> Optional[ProfileResponse]:
    """Get a profile by user_id."""
    doc = profiles_table.get(_Q.user_id == user_id)
    if doc is None:
        return None
    return _doc_to_response(doc)


def update_profile(user_id: str, data: ProfileUpdate) -> ProfileResponse:
    """Update a profile. Creates one if it doesn't exist."""
    doc = profiles_table.get(_Q.user_id == user_id)

    updates = {}
    if data.name is not None:
        updates["name"] = data.name
    if data.phone is not None:
        updates["phone"] = data.phone
    if data.address is not None:
        updates["address"] = data.address

    if doc is not None:
        if updates:
            profiles_table.update(updates, doc_ids=[doc.doc_id])
        doc = profiles_table.get(_Q.user_id == user_id)
        return _doc_to_response(doc)
    else:
        new_doc = {"user_id": user_id}
        new_doc.update(updates)
        doc_id = profiles_table.insert(new_doc)
        profiles_table.update({"doc_id": doc_id}, doc_ids=[doc_id])
        doc = profiles_table.get(_Q.doc_id == doc_id)
        return _doc_to_response(doc)
