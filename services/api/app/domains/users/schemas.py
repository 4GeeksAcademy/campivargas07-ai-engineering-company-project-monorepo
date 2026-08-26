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
    employee = "employee"


class UserCreate(BaseModel):
    email: str = Field(..., description="User email address (unique)")
    password: str = Field(..., min_length=6, description="User password (min 6 chars)")
    role: UserRole = Field(default=UserRole.admin, description="User role")
    name: str | None = Field(default=None, description="Display name for linked profile")
    phone: str | None = Field(default=None, description="Phone for linked profile")
    address: str | None = Field(default=None, description="Address for linked profile")


class UserUpdate(BaseModel):
    email: str | None = Field(default=None, description="New email address")
    role: UserRole | None = Field(default=None, description="New role (admin only)")


class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str


class UserListResponse(BaseModel):
    users: list[UserResponse]
    total: int
