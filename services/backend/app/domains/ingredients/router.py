"""router.py — Brasaland · Endpoints de Ingredientes

CRUD completo: GET (lista paginada con filtros), POST, GET/{id},
PUT/{id} y DELETE/{id} (borrado lógico si tiene inventario).
Escritura protegida con JWT (Bearer token).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.common.schemas import Page, clamp_page
from app.common.security import get_current_user
from app.database import get_db
from app.domains.auth.models import Usuario
from app.domains.ingredients.schemas import (
    IngredienteCreate,
    IngredienteOut,
    IngredienteUpdate,
)
from app.domains.ingredients.service import IngredienteService

router = APIRouter(prefix="/api/v1/ingredientes", tags=["ingredientes"])


def _service_error(exc: ValueError) -> HTTPException:
    """Convierte errores de reglas de negocio en HTTP 400."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=Page[IngredienteOut])
def listar_ingredientes(
    page: int = Query(1, ge=1, description="Número de página"),
    size: int = Query(20, ge=1, le=100, description="Registros por página"),
    activo: bool | None = Query(None, description="Filtrar por estado"),
    proveedor_id: int | None = Query(None, description="Filtrar por proveedor"),
    search: str | None = Query(None, max_length=80, description="Buscar por nombre o código"),
    db: Session = Depends(get_db),
) -> Page[IngredienteOut]:
    """Lista ingredientes con paginación y filtros opcionales."""
    page, size = clamp_page(page, size)
    items, total = IngredienteService.listar(
        db, page=page, size=size, activo=activo, proveedor_id=proveedor_id, search=search
    )
    return Page(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.post("", response_model=IngredienteOut, status_code=status.HTTP_201_CREATED)
def crear_ingrediente(
    payload: IngredienteCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> Ingrediente:
    """Crea un ingrediente (201). Requiere Bearer token."""
    try:
        return IngredienteService.crear(db, payload)
    except ValueError as exc:
        raise _service_error(exc) from exc


@router.get("/{ingrediente_id}", response_model=IngredienteOut)
def obtener_ingrediente(
    ingrediente_id: int, db: Session = Depends(get_db)
) -> Ingrediente:
    """Obtiene el detalle de un ingrediente por ID (404 si no existe)."""
    obj = IngredienteService.obtener(db, ingrediente_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingrediente no encontrado")
    return obj


@router.put("/{ingrediente_id}", response_model=IngredienteOut)
def actualizar_ingrediente(
    ingrediente_id: int,
    payload: IngredienteUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> Ingrediente:
    """Actualiza un ingrediente (PUT parcial). Requiere Bearer token."""
    try:
        obj = IngredienteService.actualizar(db, ingrediente_id, payload)
    except ValueError as exc:
        raise _service_error(exc) from exc
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingrediente no encontrado")
    return obj


@router.delete("/{ingrediente_id}", status_code=status.HTTP_200_OK)
def eliminar_ingrediente(
    ingrediente_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> dict[str, object]:
    """Elimina un ingrediente. Si tiene inventario → borrado lógico (200)."""
    encontrado, logico = IngredienteService.eliminar(db, ingrediente_id)
    if not encontrado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ingrediente no encontrado")
    if logico:
        return {
            "eliminado": True,
            "modo": "borrado_logico",
            "detalle": "El ingrediente tiene historial de inventario; se desactivó (activo=false)",
        }
    return {"eliminado": True, "modo": "fisico", "detalle": "Ingrediente eliminado"}