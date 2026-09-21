"""
router.py — Brasaland · Inventory HTTP API Endpoints

Prefix: /inventory
Endpoints:
- GET  /inventory/products            List ingredients with calculated stock for mandatory local_id
- POST /inventory/products            Create a new ingredient (authenticated)
- GET  /inventory/products/{id}       Get ingredient by ID with stock for mandatory local_id
- POST /inventory/orders/inbound      Record an inbound order (stock receipt, authenticated)
- POST /inventory/orders/outbound     Record an outbound order (stock consumption, authenticated)
- GET  /inventory/orders              List orders with joined ingredient details (authenticated, no N+1)
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.database import get_db
from app.domains.auth.dependencies import get_current_user

from . import service
from .schemas import (
    InboundOrderCreate,
    IngredientCreate,
    IngredientResponse,
    IngredientWithStockResponse,
    OrderListResponse,
    OrderResponse,
    OutboundOrderCreate,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def _extract_user_uuid(current_user: dict) -> uuid.UUID:
    """Extract and parse the stable UUID from the authenticated TinyDB user dict."""
    raw_uuid = current_user.get("uuid")
    if not raw_uuid:
        # Fallback if somehow uuid was not populated
        raw_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"brasaland-user-{current_user.doc_id}"))
    return uuid.UUID(str(raw_uuid))


@router.get("/products", response_model=list[IngredientWithStockResponse])
def list_products(
    local_id: str = Query(..., min_length=1, description="Mandatory restaurant location ID (e.g. MED-001)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[IngredientWithStockResponse]:
    """List all ingredients with calculated stock for the requested restaurant."""
    return service.list_products(session=db, local_id=local_id)


@router.post("/products", response_model=IngredientResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    data: IngredientCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IngredientResponse:
    """Create a new ingredient in the central catalog."""
    return service.create_ingredient(session=db, data=data)


@router.get("/products/{product_id}", response_model=IngredientWithStockResponse)
def get_product(
    product_id: uuid.UUID,
    local_id: str = Query(..., min_length=1, description="Mandatory restaurant location ID (e.g. MED-001)"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IngredientWithStockResponse:
    """Get an ingredient and its dynamic stock for the requested restaurant."""
    return service.get_product_by_id(session=db, product_id=product_id, local_id=local_id)


@router.post("/orders/inbound", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    data: InboundOrderCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """Record an authenticated inbound inventory movement (stock receipt)."""
    user_uuid = _extract_user_uuid(current_user)
    return service.create_inbound_order(session=db, data=data, user_uuid=user_uuid)


@router.post("/orders/outbound", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_outbound_order(
    data: OutboundOrderCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderResponse:
    """
    Record an authenticated outbound inventory movement (stock consumption).
    Validates stock balance under pessimistic row-level lock. Returns 400 if insufficient.
    """
    user_uuid = _extract_user_uuid(current_user)
    return service.create_outbound_order(session=db, data=data, user_uuid=user_uuid)


@router.get("/orders", response_model=OrderListResponse)
def list_orders(
    local_id: Optional[str] = Query(None, description="Filter by restaurant location"),
    ingredient_id: Optional[uuid.UUID] = Query(None, description="Filter by ingredient ID"),
    order_type: Optional[str] = Query(None, alias="type", description="Filter by 'inbound' or 'outbound'"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrderListResponse:
    """List inventory orders with joined ingredient details (no N+1 queries)."""
    return service.list_orders(
        session=db,
        local_id=local_id,
        ingredient_id=ingredient_id,
        order_type=order_type,
    )
