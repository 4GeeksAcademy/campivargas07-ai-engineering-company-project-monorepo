"""app.seed — package entrypoint for supplier seed command."""

from __future__ import annotations

from app.database import suppliers_table

INITIAL_SUPPLIERS = [
    {
        "business_id": "PROV-001",
        "nombre": "Carnes Premium Colombia S.A.S.",
        "pais": "Colombia",
        "contactoNombre": "Andres Mora",
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
        "contactoNombre": "Liliana Rios",
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
    for doc in suppliers_table.all():
        if doc.get("business_id") == business_id:
            return True
    return False


def seed() -> None:
    inserted = 0
    skipped = 0

    for supplier in INITIAL_SUPPLIERS:
        if _already_exists(supplier["business_id"]):
            skipped += 1
            continue

        suppliers_table.insert(supplier)
        inserted += 1

    for doc in suppliers_table.all():
        if "doc_id" not in doc:
            suppliers_table.update({"doc_id": doc.doc_id}, doc_ids=[doc.doc_id])

    print(f"Seed complete: {inserted} inserted, {skipped} skipped (already exist).")
    print(f"Total suppliers in database: {len(suppliers_table.all())}")


def main() -> None:
    seed()
