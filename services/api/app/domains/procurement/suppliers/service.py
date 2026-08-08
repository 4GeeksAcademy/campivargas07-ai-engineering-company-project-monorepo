"""
service.py — Brasaland · Supplier CRUD + TinyDB persistence

Centralized business logic for supplier directory operations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from tinydb import Query

from app.database import suppliers_table

from .schemas import (
    SupplierCreate,
    SupplierRateUpdate,
    SupplierResponse,
    SupplierStatusUpdate,
)

_Q = Query()


def _doc_to_response(doc) -> SupplierResponse:
    """Convert a TinyDB document to a SupplierResponse."""
    return SupplierResponse(
        id=str(doc.doc_id),
        nombre=doc["nombre"],
        pais=doc["pais"],
        contactoNombre=doc["contactoNombre"],
        contactoEmail=doc["contactoEmail"],
        contactoTelefono=doc["contactoTelefono"],
        categoriasQueProvee=doc["categoriasQueProvee"],
        tiempoEntregaDias=doc["tiempoEntregaDias"],
        montoMinimoOrden=doc["montoMinimoOrden"],
        moneda=doc["moneda"],
        status=doc["status"],
        updated_at=doc.get("updated_at"),
    )


def create_supplier(data: SupplierCreate) -> SupplierResponse:
    """Insert a new supplier and return the created object with ID."""
    doc = data.model_dump()
    doc_id = suppliers_table.insert(doc)
    # Store doc_id as a queryable field for future lookups
    suppliers_table.update({"doc_id": doc_id}, doc_ids=[doc_id])
    doc = suppliers_table.get(_Q.doc_id == doc_id)
    return _doc_to_response(doc)


def get_all_suppliers(
    country: Optional[str] = None,
    category: Optional[str] = None,
) -> List[SupplierResponse]:
    """List all suppliers, optionally filtered by country and/or category."""
    results = list(suppliers_table.all())

    if country is not None:
        results = [s for s in results if s["pais"] == country]

    if category is not None:
        results = [s for s in results if category in s["categoriasQueProvee"]]

    return [_doc_to_response(s) for s in results]


def get_supplier_by_id(doc_id: str) -> Optional[SupplierResponse]:
    """Retrieve a single supplier by TinyDB doc_id."""
    resolved = int(doc_id)
    doc = suppliers_table.get(_Q.doc_id == resolved)
    if doc is None:
        return None
    return _doc_to_response(doc)


def update_rate(doc_id: str, data: SupplierRateUpdate) -> Optional[SupplierResponse]:
    """Update montoMinimoOrden and set updated_at timestamp."""
    resolved = int(doc_id)
    doc = suppliers_table.get(_Q.doc_id == resolved)
    if doc is None:
        return None

    suppliers_table.update(
        {
            "montoMinimoOrden": data.montoMinimoOrden,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        _Q.doc_id == resolved,
    )

    updated = suppliers_table.get(_Q.doc_id == resolved)
    return _doc_to_response(updated)


def update_status(
    doc_id: str, data: SupplierStatusUpdate
) -> Optional[SupplierResponse]:
    """Update supplier status (activo / suspendido)."""
    resolved = int(doc_id)
    doc = suppliers_table.get(_Q.doc_id == resolved)
    if doc is None:
        return None

    suppliers_table.update({"status": data.status.value}, _Q.doc_id == resolved)

    updated = suppliers_table.get(_Q.doc_id == resolved)
    return _doc_to_response(updated)


def delete_supplier(doc_id: str) -> bool:
    """Delete a supplier. Returns True if deleted, False if not found."""
    resolved = int(doc_id)
    doc = suppliers_table.get(_Q.doc_id == resolved)
    if doc is None:
        return False
    suppliers_table.remove(_Q.doc_id == resolved)
    return True


def supplier_exists_by_business_id(business_id: str) -> bool:
    """Check if a supplier with the given business ID already exists."""
    for doc in suppliers_table.all():
        if doc.get("business_id") == business_id:
            return True
    return False


def count_suppliers() -> int:
    """Return total number of suppliers in the database."""
    return len(suppliers_table.all())
