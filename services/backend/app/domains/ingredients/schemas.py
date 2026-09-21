"""schemas.py — Brasaland · Ingredientes (Pydantic v2)

Separación estricta: estos schemas validan la API; los modelos
SQLAlchemy (models.py) son solo persistencia.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MONEDAS = {"COP", "USD"}
UNIDADES = {"kg", "g", "L", "ml", "unidad"}


class IngredienteBase(BaseModel):
    """Campos comunes de entrada/salida."""

    codigo: str = Field(..., min_length=2, max_length=30, examples=["ING-001"])
    nombre: str = Field(..., min_length=2, max_length=120, examples=["Pechuga de pollo"])
    unidad: str = Field("kg", examples=["kg"])
    stock_minimo: Decimal = Field(0, ge=0, examples=[Decimal("20.000")])
    costo_unitario: Decimal = Field(0, ge=0, examples=[Decimal("9500.00")])
    moneda: str = Field("COP", examples=["COP"])
    activo: bool = True
    proveedor_id: int | None = Field(None, description="FK al proveedor principal")

    @field_validator("unidad")
    @classmethod
    def validar_unidad(cls, v: str) -> str:
        if v not in UNIDADES:
            raise ValueError(f"unidad debe ser una de: {sorted(UNIDADES)}")
        return v

    @field_validator("moneda")
    @classmethod
    def validar_moneda(cls, v: str) -> str:
        if v not in MONEDAS:
            raise ValueError(f"moneda debe ser una de: {sorted(MONEDAS)}")
        return v


class IngredienteCreate(IngredienteBase):
    """Payload de creación (POST)."""


class IngredienteUpdate(BaseModel):
    """Payload de actualización parcial (PUT/PATCH): todos los campos opcionales."""

    nombre: str | None = Field(None, min_length=2, max_length=120)
    unidad: str | None = None
    stock_minimo: Decimal | None = Field(None, ge=0)
    costo_unitario: Decimal | None = Field(None, ge=0)
    moneda: str | None = None
    activo: bool | None = None
    proveedor_id: int | None = None


class IngredienteOut(IngredienteBase):
    """Respuesta del API (incluye id y timestamps)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime