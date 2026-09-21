"""schemas.py — Brasaland · Schemas genéricos de la API

Paginación reutilizable para todos los endpoints de listado.
"""
from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Envelope de paginación estándar."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


def clamp_page(page: int, size: int) -> tuple[int, int]:
    """Sanitiza paginación: page >= 1 y 1 <= size <= 100."""
    return max(1, page), min(max(1, size), 100)