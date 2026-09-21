"""router.py — Brasaland · Endpoints de Inventario

- GET  /api/v1/inventario            → stock con paginación y filtro por local
- GET  /api/v1/inventario/alertas    → ingredientes bajo el mínimo (requisito del hito)
- POST /api/v1/inventario/movimientos→ transacción atómica stock + Kardex
- GET  /api/v1/inventario/{id}/movimientos → historial (Kardex)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.common.schemas import Page, clamp_page
from app.common.security import get_current_user
from app.database import get_db
from app.domains.auth.models import Usuario
from app.domains.ingredients.models import InventarioLocal
from app.domains.inventory.schemas import (
    AlertaInventarioOut,
    InventarioLocalOut,
    MovimientoCreate,
    MovimientoOut,
    MovimientoResultado,
)
from app.domains.inventory.service import InventarioError, InventarioService

router = APIRouter(prefix="/api/v1/inventario", tags=["inventario"])


@router.get("", response_model=Page[InventarioLocalOut])
def listar_stock(
    local_id: int | None = Query(None, description="Filtrar por local"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> Page[InventarioLocalOut]:
    """Stock actual por local e ingrediente."""
    page, size = clamp_page(page, size)
    items, total = InventarioService.listar_stock(db, local_id=local_id, page=page, size=size)
    return Page(items=items, total=total, page=page, size=size, pages=(total + size - 1) // size)


@router.get("/alertas", response_model=list[AlertaInventarioOut])
def alertas_inventario(
    local_id: int | None = Query(None, description="Alertas de un solo local"),
    db: Session = Depends(get_db),
) -> list[AlertaInventarioOut]:
    """Ingredientes con stock por debajo del mínimo (quiebres potenciales)."""
    return InventarioService.alertas(db, local_id=local_id)


@router.post(
    "/movimientos",
    response_model=MovimientoResultado,
    status_code=status.HTTP_201_CREATED,
)
def registrar_movimiento(
    payload: MovimientoCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
) -> MovimientoResultado:
    """Registra un movimiento (entrada/salida/ajuste) y actualiza el stock.

    Todo ocurre en una única transacción de PostgreSQL: si falla la
    validación, no se toca ni el stock ni el historial (rollback).
    Requiere Bearer token.
    """
    try:
        inv = InventarioService.registrar_movimiento(db, payload)
    except InventarioError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    ultimo = InventarioService.movimientos_de_inventario(db, inv.id, limite=1)[0]
    return MovimientoResultado(movimiento=MovimientoOut.model_validate(ultimo),
                               inventario=InventarioLocalOut.model_validate(inv))


@router.get("/{inventario_id}/movimientos", response_model=list[MovimientoOut])
def movimientos_inventario(
    inventario_id: int,
    limite: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[MovimientoOut]:
    """Historial (Kardex) de movimientos de un registro de inventario."""
    inv = db.get(InventarioLocal, inventario_id)
    if inv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Registro de inventario no encontrado")
    return InventarioService.movimientos_de_inventario(db, inventario_id, limite=limite)