"""schemas.py — Brasaland · Inventario (Pydantic v2)"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

TIPOS_MOVIMIENTO = {"entrada", "salida", "ajuste"}


class InventarioLocalOut(BaseModel):
    """Stock de un ingrediente en un local."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    local_id: int
    ingrediente_id: int
    cantidad_actual: Decimal
    cantidad_minima: Decimal
    necesita_reposicion: bool
    updated_at: datetime


class AlertaInventarioOut(BaseModel):
    """Item de alerta: ingrediente bajo el mínimo en un local."""

    model_config = ConfigDict(from_attributes=True)

    inventario_id: int
    local_id: int
    local_nombre: str
    local_ciudad: str
    pais: str
    ingrediente_id: int
    ingrediente_codigo: str
    ingrediente_nombre: str
    cantidad_actual: Decimal
    cantidad_minima: Decimal
    deficit: Decimal


class MovimientoCreate(BaseModel):
    """Payload para registrar un movimiento de inventario."""

    local_id: int = Field(..., gt=0, examples=[1])
    ingrediente_id: int = Field(..., gt=0, examples=[1])
    tipo: str = Field(..., examples=["entrada"])
    cantidad: Decimal = Field(..., gt=0, examples=[Decimal("15.500")])
    motivo: str | None = Field(None, max_length=300, examples=["Compra a proveedor"])

    @field_validator("tipo")
    @classmethod
    def validar_tipo(cls, v: str) -> str:
        if v not in TIPOS_MOVIMIENTO:
            raise ValueError(f"tipo debe ser uno de: {sorted(TIPOS_MOVIMIENTO)}")
        return v


class MovimientoOut(BaseModel):
    """Respuesta del movimiento registrado."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    inventario_local_id: int
    tipo: str
    cantidad: Decimal
    motivo: str | None
    created_at: datetime


class MovimientoResultado(BaseModel):
    """Resultado de la transacción: movimiento + stock actualizado."""

    movimiento: MovimientoOut
    inventario: InventarioLocalOut