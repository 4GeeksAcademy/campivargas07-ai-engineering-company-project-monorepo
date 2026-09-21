"""schemas.py — Brasaland · Proveedores y vínculo N:M (Pydantic v2)"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PAISES = {"CO", "US"}


class ProveedorBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120, examples=["Carnes del Valle"])
    contacto: str | None = Field(None, max_length=120)
    telefono: str | None = Field(None, max_length=30)
    pais: str = Field("CO", examples=["CO"])
    dias_entrega: int = Field(3, ge=0, le=60)
    activo: bool = True

    @field_validator("pais")
    @classmethod
    def validar_pais(cls, v: str) -> str:
        if v not in PAISES:
            raise ValueError(f"pais debe ser uno de: {sorted(PAISES)}")
        return v


class ProveedorCreate(ProveedorBase):
    """Payload de creación."""


class ProveedorUpdate(BaseModel):
    """Actualización parcial."""

    nombre: str | None = Field(None, min_length=2, max_length=120)
    contacto: str | None = Field(None, max_length=120)
    telefono: str | None = Field(None, max_length=30)
    pais: str | None = None
    dias_entrega: int | None = Field(None, ge=0, le=60)
    activo: bool | None = None


class ProveedorOut(ProveedorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class LocalProveedorCreate(BaseModel):
    """Payload para vincular un proveedor a un local (N:M)."""

    es_principal: bool = False
    precio_acordado: Decimal | None = Field(None, ge=0)
    lead_time_dias: int = Field(3, ge=0, le=60)


class LocalProveedorOut(BaseModel):
    """Vínculo N:M con datos del proveedor anidados."""

    local_id: int
    proveedor_id: int
    es_principal: bool
    precio_acordado: Decimal | None
    lead_time_dias: int
    proveedor: ProveedorOut