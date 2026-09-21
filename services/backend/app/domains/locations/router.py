"""router.py — Brasaland · Endpoints de Locales"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.common.schemas import Page, clamp_page
from app.common.security import get_current_user
from app.database import get_db
from app.domains.auth.models import Usuario
from app.domains.locations.schemas import LocalCreate, LocalOut, LocalUpdate
from app.domains.locations.service import LocalService

router = APIRouter(prefix="/api/v1/locales", tags=["locales"])


@router.get("", response_model=Page[LocalOut])
def listar_locales(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    pais: str | None = Query(None, description="Filtrar por país (CO | US)"),
    db: Session = Depends(get_db),
) -> Page[LocalOut]:
    """Lista locales de la cadena con paginación y filtro por país."""
    page, size = clamp_page(page, size)
    items, total = LocalService.listar(db, page=page, size=size, pais=pais)
    return Page(items=items, total=total, page=page, size=size, pages=(total + size - 1) // size)


@router.post("", response_model=LocalOut, status_code=status.HTTP_201_CREATED)
def crear_local(
    payload: LocalCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> LocalCreate:
    """Crea un local. La moneda se asigna automáticamente según el país (CO→COP, US→USD)."""
    return LocalService.crear(db, payload)


@router.get("/{local_id}", response_model=LocalOut)
def obtener_local(local_id: int, db: Session = Depends(get_db)) -> LocalOut:
    obj = LocalService.obtener(db, local_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Local no encontrado")
    return obj


@router.put("/{local_id}", response_model=LocalOut)
def actualizar_local(
    local_id: int,
    payload: LocalUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> LocalOut:
    obj = LocalService.actualizar(db, local_id, payload)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Local no encontrado")
    return obj


@router.delete("/{local_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_local(
    local_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> None:
    """Elimina un local y sus registros dependientes (cascada). 204 sin cuerpo."""
    if not LocalService.eliminar(db, local_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Local no encontrado")
    return None