"""
schemas.py — Brasaland · Authentication Pydantic models
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="User password")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str


class ProfileOut(BaseModel):
    id: str
    user_id: str
    name: str | None = None
    phone: str | None = None
    address: str | None = None


class AuthMeResponse(BaseModel):
    user: UserOut
    profile: ProfileOut | None = None


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., description="User email address")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=6, description="New password")


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password")


class MessageResponse(BaseModel):
    detail: str
