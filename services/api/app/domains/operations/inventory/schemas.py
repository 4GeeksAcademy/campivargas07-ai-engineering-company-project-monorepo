"""
schemas.py — Brasaland · Inventory domain Pydantic schemas (Request / Response DTOs)

Strictly separated from SQLModel ORM models. No endpoint returns ORM instances directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IngredientCategory(str, Enum):
    carne = "carne"
    verdura = "verdura"
    salsa = "salsa"
    bebida = "bebida"
    empaque = "empaque"
    limpieza = "limpieza"


class IngredientCreate(BaseModel):
    sku: str = Field(..., min_length=1, max_length=50, description="SKU identifier, e.g. ING-001")
    name: str = Field(..., min_length=1, max_length=150, description="Ingredient name")
    category: IngredientCategory = Field(..., description="Ingredient category")
    unit_of_measure: str = Field(..., min_length=1, max_length=30, description="Unit of measure, e.g. kg, litros")
    minimum_stock: Decimal = Field(default=Decimal("0.0"), ge=0, description="Non-negative minimum stock threshold")
    perishable: bool = Field(default=False, description="Whether the ingredient is perishable")


class IngredientResponse(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    category: str
    unit_of_measure: str
    minimum_stock: Decimal
    perishable: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IngredientWithStockResponse(BaseModel):
    id: uuid.UUID
    sku: str
    name: str
    category: str
    unit_of_measure: str
    minimum_stock: Decimal
    perishable: bool
    created_at: datetime
    local_id: str = Field(..., description="Restaurant location ID for which current_stock is calculated")
    current_stock: Decimal = Field(..., description="Dynamic stock: SUM(inbound) - SUM(outbound) for local_id")

    model_config = ConfigDict(from_attributes=True)


class InboundOrderCreate(BaseModel):
    ingredient_id: uuid.UUID = Field(..., description="Target ingredient UUID")
    local_id: str = Field(..., min_length=1, max_length=50, description="Destination restaurant location ID")
    quantity: Decimal = Field(..., gt=0, description="Strictly positive inbound quantity")


class OutboundOrderCreate(BaseModel):
    ingredient_id: uuid.UUID = Field(..., description="Target ingredient UUID")
    local_id: str = Field(..., min_length=1, max_length=50, description="Source restaurant location ID")
    quantity: Decimal = Field(..., gt=0, description="Strictly positive outbound quantity")


class OrderResponse(BaseModel):
    id: uuid.UUID
    type: Literal["inbound", "outbound"]
    ingredient_id: uuid.UUID
    ingredient_sku: str
    ingredient_name: str
    local_id: str
    quantity: Decimal
    user_uuid: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    orders: list[OrderResponse]
    total: int
