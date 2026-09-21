"""
service.py — Brasaland · Inventory domain business service

Coordinates domain rules, validation, and error translation.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException, status
from sqlmodel import Session

from . import repository
from .schemas import (
    InboundOrderCreate,
    IngredientCreate,
    IngredientResponse,
    IngredientWithStockResponse,
    OrderListResponse,
    OrderResponse,
    OutboundOrderCreate,
)


def create_ingredient(session: Session, data: IngredientCreate) -> IngredientResponse:
    """Create a new ingredient, ensuring SKU uniqueness."""
    existing = repository.get_ingredient_by_sku(session, data.sku)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An ingredient with SKU '{data.sku}' already exists",
        )

    ingredient = repository.create_ingredient(session, data)
    return IngredientResponse.model_validate(ingredient)


def list_products(session: Session, local_id: str) -> list[IngredientWithStockResponse]:
    """List all ingredients with dynamic stock for the specified local_id."""
    items = repository.list_ingredients_with_stock(session, local_id)
    responses: list[IngredientWithStockResponse] = []
    for ing, stock in items:
        responses.append(
            IngredientWithStockResponse(
                id=ing.id,
                sku=ing.sku,
                name=ing.name,
                category=ing.category,
                unit_of_measure=ing.unit_of_measure,
                minimum_stock=ing.minimum_stock,
                perishable=ing.perishable,
                created_at=ing.created_at,
                local_id=local_id,
                current_stock=stock,
            )
        )
    return responses


def get_product_by_id(
    session: Session, product_id: uuid.UUID, local_id: str
) -> IngredientWithStockResponse:
    """Retrieve an ingredient with dynamic stock for the specified local_id."""
    ing = repository.get_ingredient_by_id(session, product_id)
    if ing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID '{product_id}' not found",
        )

    stock = repository.get_stock_for_ingredient_and_local(session, product_id, local_id)
    return IngredientWithStockResponse(
        id=ing.id,
        sku=ing.sku,
        name=ing.name,
        category=ing.category,
        unit_of_measure=ing.unit_of_measure,
        minimum_stock=ing.minimum_stock,
        perishable=ing.perishable,
        created_at=ing.created_at,
        local_id=local_id,
        current_stock=stock,
    )


def create_inbound_order(
    session: Session, data: InboundOrderCreate, user_uuid: uuid.UUID
) -> OrderResponse:
    """Create an authenticated inbound movement."""
    ing = repository.get_ingredient_by_id(session, data.ingredient_id)
    if ing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID '{data.ingredient_id}' not found",
        )

    entry = repository.create_inbound_entry(
        session=session,
        ingredient_id=data.ingredient_id,
        local_id=data.local_id,
        quantity=data.quantity,
        user_uuid=user_uuid,
    )

    return OrderResponse(
        id=entry.id,
        type="inbound",
        ingredient_id=entry.ingredient_id,
        ingredient_sku=ing.sku,
        ingredient_name=ing.name,
        local_id=entry.local_id,
        quantity=entry.quantity,
        user_uuid=entry.user_uuid,
        created_at=entry.created_at,
    )


def create_outbound_order(
    session: Session, data: OutboundOrderCreate, user_uuid: uuid.UUID
) -> OrderResponse:
    """Create an authenticated outbound movement with atomic stock validation."""
    ing = repository.get_ingredient_by_id(session, data.ingredient_id)
    if ing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingredient with ID '{data.ingredient_id}' not found",
        )

    try:
        exit_rec = repository.create_outbound_exit_with_lock(
            session=session,
            ingredient_id=data.ingredient_id,
            local_id=data.local_id,
            quantity=data.quantity,
            user_uuid=user_uuid,
        )
    except repository.InsufficientStockError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return OrderResponse(
        id=exit_rec.id,
        type="outbound",
        ingredient_id=exit_rec.ingredient_id,
        ingredient_sku=ing.sku,
        ingredient_name=ing.name,
        local_id=exit_rec.local_id,
        quantity=exit_rec.quantity,
        user_uuid=exit_rec.user_uuid,
        created_at=exit_rec.created_at,
    )


def list_orders(
    session: Session,
    local_id: Optional[str] = None,
    ingredient_id: Optional[uuid.UUID] = None,
    order_type: Optional[str] = None,
) -> OrderListResponse:
    """List all orders (inbound/outbound) matching optional filters without N+1 queries."""
    orders = repository.list_orders(
        session=session,
        local_id=local_id,
        ingredient_id=ingredient_id,
        order_type=order_type,
    )
    return OrderListResponse(orders=orders, total=len(orders))
