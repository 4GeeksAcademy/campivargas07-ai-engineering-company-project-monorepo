"""
schemas.py — Brasaland · Profile Pydantic models
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, description="Display name")
    phone: str | None = Field(default=None, description="Phone number")
    address: str | None = Field(default=None, description="Address")


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str | None = None
    phone: str | None = None
    address: str | None = None
