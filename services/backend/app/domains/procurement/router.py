"""router.py — Brasaland · Endpoints de Proveedores (CRUD + N:M con locales)"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.common.schemas import Page, clamp_page
from app.common.security import get_current_user
from app.database import get_db
from app.domains.auth.models import Usuario
from app.domains.procurement.schemas import (
    LocalProveedorCreate,
    LocalProveedorOut,
    ProveedorCreate,
    ProveedorOut,
    ProveedorUpdate,
)
from app.domains.procurement.service import ProveedorError, ProveedorService

router = APIRouter(prefix="/api/v1/proveedores", tags=["proveedores"])


def _to_local_proveedor_out(vinculo) -> LocalProveedorOut:
    """Serializa el vínculo N:M anidando el proveedor."""
    return LocalProveedorOut(
        local_id=vinculo.local_id,
        proveedor_id=vinculo.proveedor_id,
        es_principal=vinculo.es_principal,
        precio_acordado=vinculo.precio_acordado,
        lead_time_dias=vinculo.lead_time_dias,
        proveedor=ProveedorOut.model_validate(vinculo.proveedor),
    )


@router.get("", response_model=Page[ProveedorOut])
def listar_proveedores(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    pais: str | None = Query(None, description="Filtrar por país (CO | US)"),
    db: Session = Depends(get_db),
) -> Page[ProveedorOut]:
    """Lista proveedores con paginación y filtro por país."""
    page, size = clamp_page(page, size)
    items, total = ProveedorService.listar(db, page=page, size=size, pais=pais)
    return Page(items=items, total=total, page=page, size=size, pages=(total + size - 1) // size)


@router.post("", response_model=ProveedorOut, status_code=status.HTTP_201_CREATED)
def crear_proveedor(
    payload: ProveedorCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> ProveedorOut:
    """Crea un proveedor (nombre único). Requiere Bearer token."""
    try:
        return ProveedorService.crear(db, payload)
    except ProveedorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/{proveedor_id}", response_model=ProveedorOut)
def obtener_proveedor(proveedor_id: int, db: Session = Depends(get_db)) -> ProveedorOut:
    obj = ProveedorService.obtener(db, proveedor_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    return obj


@router.put("/{proveedor_id}", response_model=ProveedorOut)
def actualizar_proveedor(
    proveedor_id: int,
    payload: ProveedorUpdate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> ProveedorOut:
    """Actualiza un proveedor (PUT parcial). Requiere Bearer token."""
    try:
        obj = ProveedorService.actualizar(db, proveedor_id, payload)
    except ProveedorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    return obj


@router.delete("/{proveedor_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_proveedor(
    proveedor_id: int,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> None:
    if not ProveedorService.eliminar(db, proveedor_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    return None


@router.post(
    "/{proveedor_id}/locales/{local_id}",
    response_model=LocalProveedorOut,
    status_code=status.HTTP_201_CREATED,
)
def vincular_proveedor_local(
    proveedor_id: int,
    local_id: int,
    payload: LocalProveedorCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> LocalProveedorOut:
    """Vincula un proveedor a un local (relación N:M con condiciones comerciales)."""
    try:
        vinculo = ProveedorService.vincular_local(db, local_id, proveedor_id, payload)
    except ProveedorError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return _to_local_proveedor_out(vinculo)


@router.get("/{proveedor_id}/locales", response_model=list[LocalProveedorOut])
def locales_del_proveedor(
    proveedor_id: int, db: Session = Depends(get_db)
) -> list[LocalProveedorOut]:
    """Locales atendidos por el proveedor con precio acordado y lead time."""
    if ProveedorService.obtener(db, proveedor_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proveedor no encontrado")
    vinculos = ProveedorService.locales_del_proveedor(db, proveedor_id)
    return [_to_local_proveedor_out(v) for v in vinculos]