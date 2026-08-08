"""
schemas.py — Brasaland · Supplier directory Pydantic models

Derived from src/types/models.ts and src/utils/validations.ts.
Fields: nombre, pais, categoriasQueProvee, montoMinimoOrden, updated_at, status.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Enums / Literals (mirroring TS types) ---

class Pais(str, Enum):
    Colombia = "Colombia"
    USA = "USA"


class Moneda(str, Enum):
    COP = "COP"
    USD = "USD"


class CategoriaIngrediente(str, Enum):
    carne = "carne"
    verdura = "verdura"
    salsa = "salsa"
    bebida = "bebida"
    empaque = "empaque"
    limpieza = "limpieza"


class SupplierStatus(str, Enum):
    activo = "activo"
    suspendido = "suspendido"


# --- Base (shared fields) ---

class SupplierBase(BaseModel):
    nombre: str = Field(..., min_length=1, description="Nombre del proveedor")
    pais: Pais
    contactoNombre: str = Field(..., min_length=1, description="Nombre de contacto")
    contactoEmail: str = Field(..., description="Email de contacto")
    contactoTelefono: str = Field(..., min_length=1, description="Teléfono de contacto")
    categoriasQueProvee: List[CategoriaIngrediente] = Field(
        ..., min_length=1, description="Categorías de ingredientes que provee"
    )
    tiempoEntregaDias: int = Field(
        ..., ge=1, le=30, description="Tiempo de entrega estimado en días"
    )
    montoMinimoOrden: float = Field(
        ..., gt=0, description="Monto mínimo de orden (tarifa)"
    )
    moneda: Moneda


# --- Input: Create ---

class SupplierCreate(SupplierBase):
    status: SupplierStatus = Field(
        default=SupplierStatus.activo,
        description="Estado del proveedor (activo o suspendido)",
    )


# --- Input: Patch Rate ---

class SupplierRateUpdate(BaseModel):
    montoMinimoOrden: float = Field(
        ..., gt=0, description="Nuevo monto mínimo de orden (tarifa)"
    )


# --- Input: Patch Status ---

class SupplierStatusUpdate(BaseModel):
    status: SupplierStatus


# --- Output: Supplier ---

class SupplierResponse(SupplierBase):
    id: str = Field(..., description="ID único del proveedor (TinyDB doc_id)")
    status: SupplierStatus
    updated_at: Optional[str] = Field(
        default=None,
        description="Timestamp de última actualización de tarifa (ISO 8601)",
    )


# --- List Response ---

class SupplierListResponse(BaseModel):
    suppliers: List[SupplierResponse]
    total: int
