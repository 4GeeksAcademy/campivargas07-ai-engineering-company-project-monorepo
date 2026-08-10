"""
schemas.py — Brasaland · Supplier Pydantic models
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SupplierCreate(BaseModel):
    """Schema for creating a new supplier."""
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=100)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    nit: Optional[str] = None
    notes: Optional[str] = None


class SupplierResponse(BaseModel):
    """Schema for supplier detail response."""
    id: str
    name: str
    category: str
    status: str = "active"
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    address: Optional[str] = None
    nit: Optional[str] = None
    notes: Optional[str] = None
    tariff: Optional[float] = None
    currency: str = "COP"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class SupplierListResponse(BaseModel):
    """Schema for supplier list response."""
    suppliers: list[SupplierResponse]
    total: int


class SupplierRateUpdate(BaseModel):
    """Schema for updating supplier tariff."""
    tariff: float = Field(..., ge=0)
    currency: str = "COP"


class SupplierStatusUpdate(BaseModel):
    """Schema for updating supplier status."""
    status: str = Field(..., pattern="^(active|suspended)$")
