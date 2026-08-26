"""
router.py — Brasaland · User management endpoints

POST   /users          Register a new user (public)
GET    /users          List all users (authenticated)
GET    /users/{id}     Get user by ID (authenticated)
PUT    /users/{id}     Update user (admin or self)
DELETE /users/{id}     Delete user (admin only)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.domains.auth.dependencies import get_current_user

from .schemas import UserCreate, UserListResponse, UserResponse, UserUpdate
from . import service

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=201)
def create_user(data: UserCreate) -> UserResponse:
    """Register a new user. Profile fields (name, phone, address) are optional."""
    return service.create_user(data)


@router.get("", response_model=UserListResponse)
def list_users(
    current_user: dict = Depends(get_current_user),
) -> UserListResponse:
    """List all users. Requires authentication."""
    users = service.get_all_users()
    return UserListResponse(users=users, total=len(users))


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    """Get a user by ID. Requires authentication."""
    user = service.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    data: UserUpdate,
    current_user: dict = Depends(get_current_user),
) -> UserResponse:
    """Update user credentials. Only admin or the user themselves."""
    caller_id = str(current_user.doc_id)
    caller_role = current_user.get("role", "user")

    if caller_id != user_id and caller_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own profile unless you are an admin",
        )

    if data.role is not None and caller_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can change user roles",
        )

    user = service.update_user(user_id, data)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}")
def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Delete a user and their linked profile. Admin only."""
    caller_role = current_user.get("role", "user")
    if caller_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can delete users",
        )
    deleted = service.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User not found")
    return {"detail": "User and linked profile deleted"}
