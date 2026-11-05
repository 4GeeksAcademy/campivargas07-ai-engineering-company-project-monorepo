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

import logging

_supplier_audit_logger = logging.getLogger("brasaland.supplier_audit")

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.common.cache import TTLCache, build_key, normalize_filter
from app.domains.auth.dependencies import get_current_user

from .schemas import (
    DeleteResponse,
    SupplierConfirmationRequest,
    SupplierConfirmationResponse,
    SupplierCreate,
    SupplierListResponse,
    SupplierRateUpdate,
    SupplierResponse,
    SupplierStatusUpdate,
)
from . import confirmation
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
    # Keep the cache key semantically identical to TinyDB filtering: the
    # service performs exact equality/membership on the original values.
    generation = cache.generation("suppliers:")
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
    cache.set_if_generation(
        key,
        response,
        prefix="suppliers:",
        generation=generation,
        ttl=LIST_TTL_SECONDS,
    )
    return response


# ── GET /api/suppliers/{id} ──────────────────────────────────
@router.get("/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: str) -> SupplierResponse:
    """Get a single supplier by ID (cached, TTL 120s). 404s are never cached."""
    key = build_key(DETAIL_KEY_PREFIX, f"id={supplier_id}")
    generation = cache.generation("suppliers:")
    hit, cached = cache.get(key)
    if hit:
        return cached
    supplier = service.get_supplier_by_id(supplier_id)
    if supplier is None:
        # Important: raise BEFORE caching — negative responses are not stored.
        raise HTTPException(status_code=404, detail="Supplier not found")
    cache.set_if_generation(
        key,
        supplier,
        prefix="suppliers:",
        generation=generation,
        ttl=DETAIL_TTL_SECONDS,
    )
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


# ── POST /api/suppliers/{id}/confirm ─────────────────────────
@router.post("/{supplier_id}/confirm", response_model=SupplierConfirmationResponse)
def confirm_supplier_action(
    supplier_id: str,
    body: SupplierConfirmationRequest,
    current_user: dict = Depends(get_current_user),
) -> SupplierConfirmationResponse:
    """Create a short-lived, single-use confirmation for an irreversible supplier action."""
    from .schemas import SupplierStatus

    if body.action == "status_change":
        if body.status is None:
            raise HTTPException(status_code=422, detail="status requerido para status_change.")
        params = {"status": body.status.value}
    elif body.action == "delete":
        params = {}
    else:
        raise HTTPException(status_code=422, detail="Acción no soportada.")

    # Ensure supplier exists.
    existing = service.get_supplier_by_id(supplier_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    result = confirmation.create_confirmation(
        supplier_id=supplier_id,
        action=body.action,
        params=params,
        actor_uuid=str(current_user.get("uuid")),
    )
    return SupplierConfirmationResponse(
        confirmation_id=result["confirmation_id"],
        expires_at=result["expires_at"],
    )


# ── PATCH /api/suppliers/{id}/status ─────────────────────────
@router.patch("/{supplier_id}/status", response_model=SupplierResponse)
def update_supplier_status(
    supplier_id: str,
    data: SupplierStatusUpdate,
    current_user: dict = Depends(get_current_user),
) -> SupplierResponse:
    """Activate or suspend a supplier. Requires a valid human confirmation."""
    if not data.confirmation_id:
        raise HTTPException(status_code=403, detail="Confirmación humana requerida.")
    ok = confirmation.validate_and_consume(
        confirmation_id=data.confirmation_id,
        supplier_id=supplier_id,
        action="status_change",
        params={"status": data.status.value},
        actor_uuid=str(current_user.get("uuid")),
    )
    if not ok:
        raise HTTPException(status_code=403, detail="Confirmación inválida, expirada o reutilizada.")

    supplier = service.update_status(supplier_id, SupplierStatusUpdate(status=data.status))
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _supplier_audit_logger.info(
        "action=supplier_status_change actor=%s supplier_id=%s new_status=%s confirmed=true",
        current_user.get("uuid"),
        supplier_id,
        data.status.value,
    )
    _invalidate_all()
    return supplier


# ── DELETE /api/suppliers/{id} ────────────────────────────────
@router.delete("/{supplier_id}", response_model=DeleteResponse)
def delete_supplier(
    supplier_id: str,
    confirmation_id: Optional[str] = Query(default=None),
    current_user: dict = Depends(get_current_user),
) -> DeleteResponse:
    """Delete a supplier. Requires a valid human confirmation."""
    if not confirmation_id:
        raise HTTPException(status_code=403, detail="Confirmación humana requerida.")
    ok = confirmation.validate_and_consume(
        confirmation_id=confirmation_id,
        supplier_id=supplier_id,
        action="delete",
        params={},
        actor_uuid=str(current_user.get("uuid")),
    )
    if not ok:
        raise HTTPException(status_code=403, detail="Confirmación inválida, expirada o reutilizada.")

    deleted = service.delete_supplier(supplier_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _supplier_audit_logger.warning(
        "action=supplier_delete actor=%s supplier_id=%s confirmed=true",
        current_user.get("uuid"),
        supplier_id,
    )
    _invalidate_all()
    return DeleteResponse(detail="Supplier deleted")
