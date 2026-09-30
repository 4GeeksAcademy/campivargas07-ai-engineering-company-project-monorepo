"""
schemas.py — Brasaland · User Pydantic models
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    admin = "admin"
    manager = "manager"
    user = "user"


class UserCreate(BaseModel):
    model_config = {"extra": "forbid"}

    email: str = Field(..., description="User email address (unique)")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    name: str | None = Field(default=None, description="Display name for linked profile")
    phone: str | None = Field(default=None, description="Phone for linked profile")
    address: str | None = Field(default=None, description="Address for linked profile")


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, description="New email address")
    role: UserRole | None = Field(default=None, description="New role (admin only)")


class UserResponse(BaseModel):
    id: str
    uuid: str | None = None
    email: str
    role: str
    is_active: bool
    created_at: str


class UserRegistrationResponse(BaseModel):
    detail: str
    id: str


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int


class DeleteResponse(BaseModel):
    detail: str
