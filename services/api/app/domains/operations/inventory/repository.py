"""
repository.py — Brasaland · Inventory persistence & query operations

Implements set-based stock aggregations, pessimistic locking on outbound movements,
and eager relations to eliminate N+1 queries.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlmodel import Session, select

from .models import Ingredient, IngredientEntry, IngredientExit
from .schemas import IngredientCreate, OrderResponse


class InsufficientStockError(Exception):
    """Raised when an outbound movement exceeds available stock."""

    def __init__(self, message: str, available: Decimal, requested: Decimal):
        super().__init__(message)
        self.available = available
        self.requested = requested


def get_ingredient_by_id(session: Session, ingredient_id: uuid.UUID) -> Optional[Ingredient]:
    """Retrieve an ingredient by primary key."""
    return session.exec(select(Ingredient).where(Ingredient.id == ingredient_id)).one_or_none()


def get_ingredient_by_sku(session: Session, sku: str) -> Optional[Ingredient]:
    """Retrieve an ingredient by unique SKU."""
    return session.exec(select(Ingredient).where(Ingredient.sku == sku)).one_or_none()


def create_ingredient(session: Session, data: IngredientCreate) -> Ingredient:
    """Create and persist a new Ingredient."""
    ingredient = Ingredient(
        sku=data.sku,
        name=data.name,
        category=data.category.value,
        unit_of_measure=data.unit_of_measure,
        minimum_stock=data.minimum_stock,
        perishable=data.perishable,
        created_at=datetime.now(timezone.utc),
    )
    session.add(ingredient)
    session.commit()
    session.refresh(ingredient)
    return ingredient


def get_stock_for_ingredient_and_local(
    session: Session, ingredient_id: uuid.UUID, local_id: str
) -> Decimal:
    """
    Calculate dynamic stock for an ingredient at a specific restaurant:
    current_stock = SUM(inbound.quantity) - SUM(outbound.quantity)
    """
    inbound_stmt = select(func.coalesce(func.sum(IngredientEntry.quantity), Decimal("0.0"))).where(
        IngredientEntry.ingredient_id == ingredient_id,
        IngredientEntry.local_id == local_id,
    )
    inbound_sum = session.exec(inbound_stmt).one()

    outbound_stmt = select(func.coalesce(func.sum(IngredientExit.quantity), Decimal("0.0"))).where(
        IngredientExit.ingredient_id == ingredient_id,
        IngredientExit.local_id == local_id,
    )
    outbound_sum = session.exec(outbound_stmt).one()

    return Decimal(str(inbound_sum)) - Decimal(str(outbound_sum))


def list_ingredients_with_stock(
    session: Session, local_id: str
) -> list[tuple[Ingredient, Decimal]]:
    """
    List all ingredients with calculated stock for the specified local_id.
    Guarantees O(1) constant queries regardless of the number of ingredients:
    1. Select all ingredients.
    2. Aggregated SUM of entries grouped by ingredient_id for local_id.
    3. Aggregated SUM of exits grouped by ingredient_id for local_id.
    """
    ingredients = session.exec(select(Ingredient).order_by(Ingredient.sku)).all()
    if not ingredients:
        return []

    # Aggregated inbound sums
    inbound_stmt = (
        select(IngredientEntry.ingredient_id, func.sum(IngredientEntry.quantity))
        .where(IngredientEntry.local_id == local_id)
        .group_by(IngredientEntry.ingredient_id)
    )
    inbounds = {row[0]: Decimal(str(row[1])) for row in session.exec(inbound_stmt).all()}

    # Aggregated outbound sums
    outbound_stmt = (
        select(IngredientExit.ingredient_id, func.sum(IngredientExit.quantity))
        .where(IngredientExit.local_id == local_id)
        .group_by(IngredientExit.ingredient_id)
    )
    outbounds = {row[0]: Decimal(str(row[1])) for row in session.exec(outbound_stmt).all()}

    results: list[tuple[Ingredient, Decimal]] = []
    for ing in ingredients:
        in_qty = inbounds.get(ing.id, Decimal("0.0"))
        out_qty = outbounds.get(ing.id, Decimal("0.0"))
        stock = in_qty - out_qty
        results.append((ing, stock))

    return results


def create_inbound_entry(
    session: Session,
    ingredient_id: uuid.UUID,
    local_id: str,
    quantity: Decimal,
    user_uuid: uuid.UUID,
) -> IngredientEntry:
    """Record an authenticated inbound inventory movement."""
    entry = IngredientEntry(
        ingredient_id=ingredient_id,
        local_id=local_id,
        quantity=quantity,
        user_uuid=user_uuid,
        created_at=datetime.now(timezone.utc),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def create_outbound_exit_with_lock(
    session: Session,
    ingredient_id: uuid.UUID,
    local_id: str,
    quantity: Decimal,
    user_uuid: uuid.UUID,
) -> IngredientExit:
    """
    Atomically verify stock and record an outbound movement.
    Uses pessimistic locking (SELECT ... FOR UPDATE) on the Ingredient row
    in PostgreSQL to prevent race conditions during concurrent exits.
    Rolls back without writing anything if requested quantity > current stock.
    """
    # 1. Lock the ingredient row for update
    lock_stmt = select(Ingredient).where(Ingredient.id == ingredient_id).with_for_update()
    ingredient = session.exec(lock_stmt).one_or_none()
    if ingredient is None:
        raise ValueError(f"Ingredient with ID '{ingredient_id}' not found")

    # 2. Calculate current stock for this local_id within the protected transaction
    current_stock = get_stock_for_ingredient_and_local(session, ingredient_id, local_id)

    # 3. Validate sufficient balance
    if current_stock < quantity:
        session.rollback()
        raise InsufficientStockError(
            f"Insufficient stock for ingredient '{ingredient.name}' (SKU: {ingredient.sku}) "
            f"in restaurant '{local_id}'. Available: {current_stock}, requested: {quantity}",
            available=current_stock,
            requested=quantity,
        )

    # 4. Insert and commit exit
    exit_record = IngredientExit(
        ingredient_id=ingredient_id,
        local_id=local_id,
        quantity=quantity,
        user_uuid=user_uuid,
        created_at=datetime.now(timezone.utc),
    )
    session.add(exit_record)
    session.commit()
    session.refresh(exit_record)
    return exit_record


def list_orders(
    session: Session,
    local_id: Optional[str] = None,
    ingredient_id: Optional[uuid.UUID] = None,
    order_type: Optional[str] = None,
) -> list[OrderResponse]:
    """
    List inbound and outbound movements joined with Ingredient data.
    Uses constant queries (O(1)) by joining directly with the Ingredient table,
    completely avoiding N+1 queries.
    """
    orders: list[OrderResponse] = []

    # Inbound entries
    if order_type in (None, "inbound"):
        entry_stmt = select(IngredientEntry, Ingredient).join(
            Ingredient, IngredientEntry.ingredient_id == Ingredient.id
        )
        if local_id:
            entry_stmt = entry_stmt.where(IngredientEntry.local_id == local_id)
        if ingredient_id:
            entry_stmt = entry_stmt.where(IngredientEntry.ingredient_id == ingredient_id)

        for entry, ing in session.exec(entry_stmt).all():
            orders.append(
                OrderResponse(
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
            )

    # Outbound exits
    if order_type in (None, "outbound"):
        exit_stmt = select(IngredientExit, Ingredient).join(
            Ingredient, IngredientExit.ingredient_id == Ingredient.id
        )
        if local_id:
            exit_stmt = exit_stmt.where(IngredientExit.local_id == local_id)
        if ingredient_id:
            exit_stmt = exit_stmt.where(IngredientExit.ingredient_id == ingredient_id)

        for exit_rec, ing in session.exec(exit_stmt).all():
            orders.append(
                OrderResponse(
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
            )

    # Sort combined movements by creation date descending
    orders.sort(key=lambda o: o.created_at, reverse=True)
    return orders
