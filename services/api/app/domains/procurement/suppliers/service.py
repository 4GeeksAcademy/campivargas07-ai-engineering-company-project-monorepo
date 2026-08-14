"""
service.py — Brasaland · Supplier CRUD operations
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.database import suppliers_table

from .schemas import SupplierCreate, SupplierRateUpdate, SupplierResponse, SupplierStatusUpdate


def _doc_to_response(doc: dict) -> SupplierResponse:
    """Convert a TinyDB document to a SupplierResponse."""
    return SupplierResponse(
        id=doc.get("id", ""),
        name=doc.get("name", ""),
        category=doc.get("category", ""),
        status=doc.get("status", "active"),
        contact_email=doc.get("contact_email"),
        contact_phone=doc.get("contact_phone"),
        address=doc.get("address"),
        nit=doc.get("nit"),
        notes=doc.get("notes"),
        tariff=doc.get("tariff"),
        currency=doc.get("currency", "COP"),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


def create_supplier(data: SupplierCreate) -> SupplierResponse:
    """Create a new supplier and return the response."""
    supplier_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": supplier_id,
        "name": data.name,
        "category": data.category,
        "status": "active",
        "contact_email": data.contact_email,
        "contact_phone": data.contact_phone,
        "address": data.address,
        "nit": data.nit,
        "notes": data.notes,
        "created_at": now,
        "updated_at": now,
    }
    suppliers_table.insert(doc)
    return _doc_to_response(doc)


def get_all_suppliers(
    country: Optional[str] = None,
    category: Optional[str] = None,
) -> list[SupplierResponse]:
    """Return all suppliers, optionally filtered by country and category."""
    results = []
    for doc in suppliers_table.all():
        if country and doc.get("country") != country:
            continue
        if category and doc.get("category") != category:
            continue
        results.append(_doc_to_response(doc))
    return results


def get_supplier_by_id(supplier_id: str) -> Optional[SupplierResponse]:
    """Return a single supplier by ID, or None if not found."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            return _doc_to_response(doc)
    return None


def update_rate(supplier_id: str, data: SupplierRateUpdate) -> Optional[SupplierResponse]:
    """Update a supplier's tariff. Returns the updated supplier or None."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            doc["tariff"] = data.tariff
            doc["currency"] = data.currency
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            suppliers_table.write_back([doc])
            return _doc_to_response(doc)
    return None


def update_status(supplier_id: str, data: SupplierStatusUpdate) -> Optional[SupplierResponse]:
    """Update a supplier's status (active/suspended). Returns the updated supplier or None."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            doc["status"] = data.status
            doc["updated_at"] = datetime.now(timezone.utc).isoformat()
            suppliers_table.write_back([doc])
            return _doc_to_response(doc)
    return None


def delete_supplier(supplier_id: str) -> bool:
    """Delete a supplier by ID. Returns True if deleted, False if not found."""
    for doc in suppliers_table.all():
        if doc.get("id") == supplier_id:
            suppliers_table.remove(doc)
            return True
    return False
