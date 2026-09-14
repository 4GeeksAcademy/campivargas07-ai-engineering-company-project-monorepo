"""router.py — Brasaland · Autenticación (JWT)

POST /api/v1/auth/token → login con OAuth2PasswordRequestForm
(form-urlencoded: username + password) y devuelve el Bearer token.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.domains.auth.models import Usuario
from app.domains.auth.schemas import TokenResponse
from app.common.security import create_access_token, verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/token", response_model=TokenResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> TokenResponse:
    """Autentica un usuario y devuelve un JWT (flujo password)."""
    user = db.query(Usuario).filter(Usuario.email == form.username).first()
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    return TokenResponse(
        access_token=create_access_token(user.email, user.rol),
        rol=user.rol,
    )