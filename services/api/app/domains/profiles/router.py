"""
router.py — Brasaland · Profile management endpoints

GET    /profiles/me     Get authenticated user's profile
PUT    /profiles/me     Update authenticated user's profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.domains.auth.dependencies import get_current_user

from .schemas import ProfileResponse, ProfileUpdate
from . import service

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(
    current_user: dict = Depends(get_current_user),
) -> ProfileResponse:
    """Return the profile linked to the authenticated user."""
    user_id = str(current_user.doc_id)
    profile = service.get_profile_by_user_id(user_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Create one first via user registration.",
        )
    return profile


@router.put("/me", response_model=ProfileResponse)
def update_my_profile(
    data: ProfileUpdate,
    current_user: dict = Depends(get_current_user),
) -> ProfileResponse:
    """Update name, phone, and address for the authenticated user's profile."""
    user_id = str(current_user.doc_id)
    return service.update_profile(user_id, data)
