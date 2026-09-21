"""schemas.py — Brasaland · Auth (Pydantic)"""
from __future__ import annotations

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Respuesta del login."""

    access_token: str
    token_type: str = "bearer"
    rol: str