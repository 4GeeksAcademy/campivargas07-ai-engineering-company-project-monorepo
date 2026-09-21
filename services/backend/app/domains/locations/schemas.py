"""schemas.py — Brasaland · Locales (Pydantic v2)"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

PAISES = {"CO", "US"}
MONEDAS = {"COP", "USD"}


class LocalBase(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=120, examples=["Brasaland Medellín"])
    ciudad: str = Field(..., min_length=2, max_length=80, examples=["Medellín"])
    pais: str = Field("CO", examples=["CO"])
    moneda: str = Field("COP", examples=["COP"])
    direccion: str | None = Field(None, max_length=200)
    activo: bool = True

    @field_validator("pais")
    @classmethod
    def validar_pais(cls, v: str) -> str:
        if v not in PAISES:
            raise ValueError(f"pais debe ser uno de: {sorted(PAISES)}")
        return v

    @field_validator("moneda")
    @classmethod
    def validar_moneda(cls, v: str) -> str:
        if v not in MONEDAS:
            raise ValueError(f"moneda debe ser una de: {sorted(MONEDAS)}")
        return v


class LocalCreate(LocalBase):
    """Payload de creación."""


class LocalUpdate(BaseModel):
    """Actualización parcial: todos los campos opcionales."""

    nombre: str | None = Field(None, min_length=2, max_length=120)
    ciudad: str | None = Field(None, min_length=2, max_length=80)
    pais: str | None = None
    moneda: str | None = None
    direccion: str | None = Field(None, max_length=200)
    activo: bool | None = None


class LocalOut(LocalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime