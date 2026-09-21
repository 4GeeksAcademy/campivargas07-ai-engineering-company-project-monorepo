"""
models.py — Brasaland · Inventory domain ORM models (SQLModel / PostgreSQL)

Entities:
- Ingredient: Core ingredient catalog without persisted stock column.
- IngredientEntry: Inbound order/movement (stock addition).
- IngredientExit: Outbound order/movement (stock consumption).
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import CheckConstraint, Column, DateTime, Numeric, String, types
from sqlmodel import Field, Relationship, SQLModel

VALID_CATEGORIES = ("carne", "verdura", "salsa", "bebida", "empaque", "limpieza")


class Ingredient(SQLModel, table=True):
    """
    Core ingredient catalog item.
    Stock is NEVER stored as a column; it is always derived dynamically
    from the sum of entries minus exits per restaurant (local_id).
    """

    __tablename__ = "ingredient"
    __table_args__ = (
        CheckConstraint("minimum_stock >= 0", name="chk_ingredient_minimum_stock_non_negative"),
        CheckConstraint(
            f"category IN {VALID_CATEGORIES!r}",
            name="chk_ingredient_category_valid",
        ),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    sku: str = Field(
        sa_column=Column(String(50), unique=True, index=True, nullable=False),
        description="Unique stock keeping unit code, e.g. ING-001",
    )
    name: str = Field(
        sa_column=Column(String(150), nullable=False),
        description="Mandatory name of the ingredient",
    )
    category: str = Field(
        sa_column=Column(String(50), nullable=False),
        description="Category: carne, verdura, salsa, bebida, empaque, limpieza",
    )
    unit_of_measure: str = Field(
        sa_column=Column(String(30), nullable=False),
        description="Unit of measure, e.g. kg, litros, unidades",
    )
    minimum_stock: Decimal = Field(
        default=Decimal("0.0"),
        sa_column=Column(Numeric(10, 2), nullable=False, default=0.0),
        description="Non-negative minimum stock threshold per location",
    )
    perishable: bool = Field(
        default=False,
        nullable=False,
        description="Whether the ingredient is perishable",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="Server-generated UTC creation timestamp",
    )

    # Relationships
    entries: List["IngredientEntry"] = Relationship(
        back_populates="ingredient",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    exits: List["IngredientExit"] = Relationship(
        back_populates="ingredient",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class IngredientEntry(SQLModel, table=True):
    """
    Inbound inventory order / receipt.
    Represents physical stock received at a specific restaurant.
    """

    __tablename__ = "ingredient_entry"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_ingredient_entry_quantity_positive"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    ingredient_id: uuid.UUID = Field(
        foreign_key="ingredient.id",
        index=True,
        nullable=False,
        description="Foreign key to the parent Ingredient",
    )
    local_id: str = Field(
        sa_column=Column(String(50), index=True, nullable=False),
        description="Restaurant location identifier (stock partition key), e.g. MED-001",
    )
    quantity: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Strictly positive quantity received",
    )
    user_uuid: uuid.UUID = Field(
        sa_column=Column(types.Uuid, index=True, nullable=False),
        description="Stable UUID of the authenticated TinyDB user who created the movement",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True, nullable=False),
        description="Server-generated UTC timestamp of the entry",
    )

    # Relationships
    ingredient: Optional[Ingredient] = Relationship(back_populates="entries")


class IngredientExit(SQLModel, table=True):
    """
    Outbound inventory order / consumption.
    Represents physical stock consumed or dispatched at a specific restaurant.
    """

    __tablename__ = "ingredient_exit"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="chk_ingredient_exit_quantity_positive"),
    )

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    ingredient_id: uuid.UUID = Field(
        foreign_key="ingredient.id",
        index=True,
        nullable=False,
        description="Foreign key to the parent Ingredient",
    )
    local_id: str = Field(
        sa_column=Column(String(50), index=True, nullable=False),
        description="Restaurant location identifier (stock partition key), e.g. MED-001",
    )
    quantity: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Strictly positive quantity consumed",
    )
    user_uuid: uuid.UUID = Field(
        sa_column=Column(types.Uuid, index=True, nullable=False),
        description="Stable UUID of the authenticated TinyDB user who created the movement",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), index=True, nullable=False),
        description="Server-generated UTC timestamp of the exit",
    )

    # Relationships
    ingredient: Optional[Ingredient] = Relationship(back_populates="exits")
