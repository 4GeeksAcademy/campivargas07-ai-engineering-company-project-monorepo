#!/usr/bin/env python3
"""
seed.py — Brasaland · Supplier directory seeder

Loads the initial supplier directory into TinyDB.
Idempotent: skips suppliers that already exist (matched by business_id).
Run with: uv run seed
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure app module is importable when run as script
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import suppliers_table  # noqa: E402

# ── Initial supplier directory (from src/demo.ts + TS validations) ──────

INITIAL_SUPPLIERS = [
    {
        "business_id": "PROV-001",
        "nombre": "Carnes Premium Colombia S.A.S.",
        "pais": "Colombia",
        "contactoNombre": "Andrés Mora",
        "contactoEmail": "andres.mora@carnespremium.co",
        "contactoTelefono": "+57 310 1234567",
        "categoriasQueProvee": ["carne"],
        "tiempoEntregaDias": 2,
        "montoMinimoOrden": 500_000,
        "moneda": "COP",
        "status": "activo",
        "updated_at": None,
    },
    {
        "business_id": "PROV-002",
        "nombre": "Florida Meat Distributors LLC",
        "pais": "USA",
        "contactoNombre": "James Walker",
        "contactoEmail": "j.walker@floridameat.com",
        "contactoTelefono": "+1 305 5550001",
        "categoriasQueProvee": ["carne", "verdura"],
        "tiempoEntregaDias": 1,
        "montoMinimoOrden": 300,
        "moneda": "USD",
        "status": "activo",
        "updated_at": None,
    },
    {
        "business_id": "PROV-003",
        "nombre": "Verduras del Campo Ltda.",
        "pais": "Colombia",
        "contactoNombre": "Liliana Ríos",
        "contactoEmail": "liliana.rios@verdurascampo.co",
        "contactoTelefono": "+57 4 6789012",
        "categoriasQueProvee": ["verdura", "salsa"],
        "tiempoEntregaDias": 1,
        "montoMinimoOrden": 200_000,
        "moneda": "COP",
        "status": "activo",
        "updated_at": None,
    },
]


def _already_exists(business_id: str) -> bool:
    """Check if a supplier with this business_id is already in the DB."""
    for doc in suppliers_table.all():
        if doc.get("business_id") == business_id:
            return True
    return False


def seed() -> None:
    """Load initial suppliers into TinyDB. Idempotent."""
    inserted = 0
    skipped = 0

    for supplier in INITIAL_SUPPLIERS:
        if _already_exists(supplier["business_id"]):
            skipped += 1
            continue

        suppliers_table.insert(supplier)
        inserted += 1

    # Store doc_id as a queryable field for all inserted suppliers
    for doc in suppliers_table.all():
        if "doc_id" not in doc:
            suppliers_table.update({"doc_id": doc.doc_id}, doc_ids=[doc.doc_id])

    # Summary
    total = len(INITIAL_SUPPLIERS)
    print(f"Seed complete: {inserted} inserted, {skipped} skipped (already exist).")
    print(f"Total suppliers in database: {len(suppliers_table.all())}")


if __name__ == "__main__":
    seed()
