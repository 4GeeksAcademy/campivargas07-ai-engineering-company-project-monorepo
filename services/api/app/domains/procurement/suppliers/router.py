"""
router.py — Brasaland · Supplier directory endpoints

POST   /api/suppliers              Create supplier       (PROTECTED)
GET    /api/suppliers              List (filter)         (PUBLIC)
GET    /api/suppliers/{id}         Detail by ID          (PUBLIC)
PATCH  /api/suppliers/{id}/rate    Update tariff         (PROTECTED)
PATCH  /api/suppliers/{id}/status  Activate / suspend    (PROTECTED)
DELETE /api/suppliers/{id}         Remove                (PROTECTED)

Caching (feature/caching-optimisation):
- GET list and GET detail are cached with explicit deterministic keys.
- TTL: list 60s, detail 120s (freshness trade-off documented in the report).
- Every mutation (create / rate / status / delete) invalidates the detail key
  AND all list variants via namespace prefix invalidation.
- 404s are raised BEFORE any cache write, so errors are never cached.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.cache import TTLCache, build_key, normalize_filter
from app.domains.auth.dependencies import get_current_user

from .schemas import (
    DeleteResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierRateUpdate,
    SupplierResponse,
    SupplierStatusUpdate,
)
from . import service

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])

# ── Cache wiring ─────────────────────────────────────────────
# One process-local cache instance; injected clock defaults to time.monotonic.
# TTLs (task spec): list ≈ 60s, detail ≈ 120s.
LIST_TTL_SECONDS = 60.0
DETAIL_TTL_SECONDS = 120.0
LIST_KEY_PREFIX = "suppliers:list:v1"
DETAIL_KEY_PREFIX = "suppliers:detail:v1"

cache = TTLCache(
    max_size=256,
    default_ttl=LIST_TTL_SECONDS,
    namespace="suppliers",
)


def _invalidate_all() -> None:
    """Invalidate every supplier list variant and every detail entry."""
    cache.invalidate_prefix("suppliers:")


# ── POST /api/suppliers ──────────────────────────────────────
@router.post("", response_model=SupplierResponse, status_code=201)
def create_supplier(
    data: SupplierCreate,
    current_user: dict = Depends(get_current_user),
) -> SupplierResponse:
    """Register a new supplier. Returns the created supplier with its ID."""
    created = service.create_supplier(data)
    _invalidate_all()
    return created


# ── GET /api/suppliers ────────────────────────────────────────
@router.get("", response_model=SupplierListResponse)
def list_suppliers(
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by product category"),
) -> SupplierListResponse:
    """List all suppliers with optional country and category filters (cached, TTL 60s)."""
    key = build_key(
        LIST_KEY_PREFIX,
        f"country={normalize_filter(country)}",
        f"category={normalize_filter(category)}",
    )
    hit, cached = cache.get(key)
    if hit:
        return cached
    suppliers = service.get_all_suppliers(country=country, category=category)
    response = SupplierListResponse(suppliers=suppliers, total=len(suppliers))
    cache.set(key, response, ttl=LIST_TTL_SECONDS)
    return response


# ── GET /api/suppliers/{id} ──────────────────────────────────
@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: str) -> SupplierResponse:
    """Get a single supplier by ID (cached, TTL 120s). 404s are never cached."""
    key = build_key(DETAIL_KEY_PREFIX, f"id={supplier_id}")
    hit, cached = cache.get(key)
    if hit:
        return cached
    supplier = service.get_supplier_by_id(supplier_id)
    if supplier is None:
        # Important: raise BEFORE caching — negative responses are not stored.
        raise HTTPException(status_code=404, detail="Supplier not found")
    cache.set(key, supplier, ttl=DETAIL_TTL_SECONDS)
    return supplier


# ── PATCH /api/suppliers/{id}/rate ───────────────────────────
@router.patch("/{supplier_id}/rate", response_model=SupplierResponse)
def update_supplier_rate(
    supplier_id: str,
    data: SupplierRateUpdate,
    current_user: dict = Depends(get_current_user),
) -> SupplierResponse:
    """Update the tariff (montoMinimoOrden) and record the change timestamp."""
    supplier = service.update_rate(supplier_id, data)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _invalidate_all()
    return supplier


# ── PATCH /api/suppliers/{id}/status ─────────────────────────
@router.patch("/{supplier_id}/status", response_model=SupplierResponse)
def update_supplier_status(
    supplier_id: str,
    data: SupplierStatusUpdate,
    current_user: dict = Depends(get_current_user),
) -> SupplierResponse:
    """Activate or suspend a supplier. Only 'activo' and 'suspendido' are allowed."""
    supplier = service.update_status(supplier_id, data)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _invalidate_all()
    return supplier


# ── DELETE /api/suppliers/{id} ────────────────────────────────
@router.delete("/{supplier_id}", response_model=DeleteResponse)
def delete_supplier(
    supplier_id: str,
    current_user: dict = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a supplier. Returns 404 if not found."""
    deleted = service.delete_supplier(supplier_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _invalidate_all()
    return DeleteResponse(detail="Supplier deleted")
