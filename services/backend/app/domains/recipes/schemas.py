"""schemas.py — Brasaland · Recetas (MongoDB, Pydantic v2)

Los documentos de recetas tienen esquema FLEXIBLE: pasos anidados,
lista variable de ingredientes con referencia a PostgreSQL (ingrediente_id)
y metadatos libres. Esto es exactamente el caso de uso de MongoDB.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class IngredienteReceta(BaseModel):
    """Ingrediente anidado dentro de la receta (referencia al SQL de PostgreSQL)."""

    ingrediente_id: int = Field(..., description="ID del ingrediente en PostgreSQL")
    nombre: str
    cantidad: float = Field(..., gt=0, examples=[0.35])
    unidad: str = Field("kg", examples=["kg"])


class PasoReceta(BaseModel):
    """Paso de preparación anidado."""

    orden: int = Field(..., ge=1)
    descripcion: str = Field(..., min_length=5)
    duracion_min: int | None = Field(None, ge=0, le=600)


class RecetaCreate(BaseModel):
    """Payload para crear una receta (documento flexible)."""

    plato: str = Field(..., min_length=3, max_length=120, examples=["Churrasco a la brasa"])
    categoria: str = Field("carnes", examples=["carnes"])
    porciones: int = Field(1, ge=1, le=100)
    ingredientes: list[IngredienteReceta] = Field(..., min_length=1)
    pasos: list[PasoReceta] = Field(..., min_length=1)
    version: int = Field(1, ge=1)
    tags: list[str] = Field(default_factory=list)
    notas_chef: str | None = None


class RecetaOut(RecetaCreate):
    """Respuesta: el documento + su _id de Mongo como string."""

    id: str = Field(..., alias="_id", description="ObjectId serializado como string")


class AuditoriaLogCreate(BaseModel):
    """Log de auditoría (escrito por el sistema, no por el cliente)."""

    entidad: str
    entidad_id: str
    accion: str
    usuario: str | None = None
    detalle: dict | None = None


class AuditoriaLogOut(AuditoriaLogCreate):
    id: str = Field(..., alias="_id")
    created_at: str