"""
router.py — Brasaland · Supplier directory endpoints

POST   /api/suppliers          Create supplier
GET    /api/suppliers          List (filter by country, category)
GET    /api/suppliers/{id}     Detail by ID
PATCH  /api/suppliers/{id}/rate    Update tariff + timestamp
PATCH  /api/suppliers/{id}/status  Activate / suspend
DELETE /api/suppliers/{id}     Remove
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .schemas import (
    SupplierCreate,
    SupplierListResponse,
    SupplierRateUpdate,
    SupplierResponse,
    SupplierStatusUpdate,
)
from . import service

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


# ── POST /api/suppliers ──────────────────────────────────────
@router.post("", response_model=SupplierResponse, status_code=201)
def create_supplier(data: SupplierCreate) -> SupplierResponse:
    """Register a new supplier. Returns the created supplier with its ID."""
    return service.create_supplier(data)


# ── GET /api/suppliers ────────────────────────────────────────
@router.get("", response_model=SupplierListResponse)
def list_suppliers(
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by product category"),
) -> SupplierListResponse:
    """List all suppliers with optional country and category filters."""
    suppliers = service.get_all_suppliers(country=country, category=category)
    return SupplierListResponse(suppliers=suppliers, total=len(suppliers))


# ── GET /api/suppliers/{id} ──────────────────────────────────
@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: str) -> SupplierResponse:
    """Get a single supplier by ID. Returns 404 if not found."""
    supplier = service.get_supplier_by_id(supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


# ── PATCH /api/suppliers/{id}/rate ───────────────────────────
@router.patch("/{supplier_id}/rate", response_model=SupplierResponse)
def update_supplier_rate(supplier_id: str, data: SupplierRateUpdate) -> SupplierResponse:
    """Update the tariff (montoMinimoOrden) and record the change timestamp."""
    supplier = service.update_rate(supplier_id, data)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


# ── PATCH /api/suppliers/{id}/status ─────────────────────────
@router.patch("/{supplier_id}/status", response_model=SupplierResponse)
def update_supplier_status(
    supplier_id: str, data: SupplierStatusUpdate
) -> SupplierResponse:
    """Activate or suspend a supplier. Only 'activo' and 'suspendido' are allowed."""
    supplier = service.update_status(supplier_id, data)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


# ── DELETE /api/suppliers/{id} ────────────────────────────────
@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: str) -> dict:
    """Delete a supplier. Returns 404 if not found."""
    deleted = service.delete_supplier(supplier_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"detail": "Supplier deleted"}
