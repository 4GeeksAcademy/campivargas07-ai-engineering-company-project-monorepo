"""
router.py — Brasaland · Authentication endpoints

POST   /auth/login     Authenticate with email/password, return JWT
GET    /auth/me        Get current authenticated user + profile
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from tinydb import Query

from app.database import profiles_table, users_table

from .dependencies import get_current_user
from .schemas import AuthMeResponse, LoginRequest, ProfileOut, TokenResponse, UserOut
from .service import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])
_Q = Query()


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest) -> TokenResponse:
    """Authenticate a user by email and password. Returns a JWT access token."""
    user = users_table.get(_Q.email == data.email)

    if user is None or not verify_password(data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    token = create_access_token(
        data={"sub": str(user.doc_id), "role": user["role"]}
    )
    return TokenResponse(access_token=token)


@router.get("/me", response_model=AuthMeResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> AuthMeResponse:
    """Return the authenticated user's credentials and linked profile."""
    user_out = UserOut(
        id=str(current_user.doc_id),
        email=current_user["email"],
        role=current_user["role"],
        is_active=current_user["is_active"],
        created_at=current_user["created_at"],
    )

    profile_doc = profiles_table.get(_Q.user_id == str(current_user.doc_id))
    profile_out = None
    if profile_doc:
        profile_out = ProfileOut(
            id=str(profile_doc.doc_id),
            user_id=profile_doc["user_id"],
            name=profile_doc.get("name"),
            phone=profile_doc.get("phone"),
            address=profile_doc.get("address"),
        )

    return AuthMeResponse(user=user_out, profile=profile_out)
