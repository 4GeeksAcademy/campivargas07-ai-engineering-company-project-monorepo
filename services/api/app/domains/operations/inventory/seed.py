"""
seed.py — Brasaland · Idempotent inventory data seed

Populates the 7 ingredients from src/demo.ts (ING-001 to ING-007) and sample
movements for MED-001 and MIA-001. Requires and verifies an existing TinyDB user.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlmodel import Session, select
from tinydb import Query

import app.database as database
from app.database import backfill_users_uuid, get_db_engine, init_db
from app.domains.operations.inventory.models import (
    Ingredient,
    IngredientEntry,
    IngredientExit,
)

# 7 core ingredients from src/demo.ts
SEED_INGREDIENTS = [
    {
        "sku": "ING-001",
        "name": "Carne de Res (kg)",
        "category": "carne",
        "unit_of_measure": "kg",
        "minimum_stock": Decimal("20.0"),
        "perishable": True,
    },
    {
        "sku": "ING-002",
        "name": "Pollo Entero (kg)",
        "category": "carne",
        "unit_of_measure": "kg",
        "minimum_stock": Decimal("15.0"),
        "perishable": True,
    },
    {
        "sku": "ING-003",
        "name": "Tomate (kg)",
        "category": "verdura",
        "unit_of_measure": "kg",
        "minimum_stock": Decimal("10.0"),
        "perishable": True,
    },
    {
        "sku": "ING-004",
        "name": "Lechuga (unidad)",
        "category": "verdura",
        "unit_of_measure": "unidades",
        "minimum_stock": Decimal("30.0"),
        "perishable": True,
    },
    {
        "sku": "ING-005",
        "name": "Salsa Chimichurri (litros)",
        "category": "salsa",
        "unit_of_measure": "litros",
        "minimum_stock": Decimal("5.0"),
        "perishable": False,
    },
    {
        "sku": "ING-006",
        "name": "Gaseosa Cola (litros)",
        "category": "bebida",
        "unit_of_measure": "litros",
        "minimum_stock": Decimal("50.0"),
        "perishable": False,
    },
    {
        "sku": "ING-007",
        "name": "Caja de Empaque",
        "category": "empaque",
        "unit_of_measure": "unidades",
        "minimum_stock": Decimal("200.0"),
        "perishable": False,
    },
]

# Movements planned to reflect exact demo.ts net stock:
# MED-001: ING-001 net 8, ING-002 net 25, ING-003 net 3
# MIA-001: ING-001 net 45, ING-006 net 10
SEED_MOVEMENTS = [
    # local_id, sku, inbound_qty, outbound_qty (net = in - out)
    ("MED-001", "ING-001", Decimal("50.0"), Decimal("42.0")),  # net: 8.0
    ("MED-001", "ING-002", Decimal("30.0"), Decimal("5.0")),   # net: 25.0
    ("MED-001", "ING-003", Decimal("10.0"), Decimal("7.0")),   # net: 3.0
    ("MIA-001", "ING-001", Decimal("60.0"), Decimal("15.0")),  # net: 45.0
    ("MIA-001", "ING-006", Decimal("50.0"), Decimal("40.0")),  # net: 10.0
]


def resolve_tinydb_user_uuid(identifier: str) -> uuid.UUID:
    """
    Verifies that the provided identifier corresponds to a real user in TinyDB.
    Accepts UUID, email, or TinyDB integer doc_id.
    Raises ValueError if user is not found.
    """
    _Q = Query()
    user_doc = None

    # Check by email
    user_doc = database.users_table.get(_Q.email == identifier)

    # Check by uuid
    if user_doc is None:
        user_doc = database.users_table.get(_Q.uuid == identifier)

    # Check by doc_id
    if user_doc is None and identifier.isdigit():
        user_doc = database.users_table.get(doc_id=int(identifier))

    if user_doc is None:
        raise ValueError(
            f"User '{identifier}' does not exist in TinyDB. "
            "Seed requires a pre-existing authenticated user identity."
        )

    # Ensure uuid is present
    user_uuid = user_doc.get("uuid")
    if not user_uuid:
        stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"brasaland-user-{user_doc.doc_id}"))
        database.users_table.update({"uuid": stable_uuid}, doc_ids=[user_doc.doc_id])
        user_uuid = stable_uuid

    return uuid.UUID(user_uuid)


def seed_inventory(
    session: Session, user_identifier: str
) -> dict[str, int]:
    """
    Idempotently seeds ingredients and inventory movements for MED-001 and MIA-001.
    Returns counts of newly created ingredients and movements.
    """
    user_uuid = resolve_tinydb_user_uuid(user_identifier)

    # 1. Seed ingredients
    created_ingredients = 0
    sku_to_ingredient: dict[str, Ingredient] = {}

    for item in SEED_INGREDIENTS:
        existing = session.exec(
            select(Ingredient).where(Ingredient.sku == item["sku"])
        ).one_or_none()

        if existing is None:
            ing = Ingredient(
                sku=item["sku"],
                name=item["name"],
                category=item["category"],
                unit_of_measure=item["unit_of_measure"],
                minimum_stock=item["minimum_stock"],
                perishable=item["perishable"],
                created_at=datetime.now(timezone.utc),
            )
            session.add(ing)
            session.flush()
            sku_to_ingredient[item["sku"]] = ing
            created_ingredients += 1
        else:
            sku_to_ingredient[item["sku"]] = existing

    session.commit()

    # 2. Seed movements idempotently
    created_movements = 0
    now = datetime.now(timezone.utc)

    for local_id, sku, in_qty, out_qty in SEED_MOVEMENTS:
        ing = sku_to_ingredient[sku]

        # Check if an entry already exists for this ingredient, local_id and quantity
        existing_entry = session.exec(
            select(IngredientEntry).where(
                IngredientEntry.ingredient_id == ing.id,
                IngredientEntry.local_id == local_id,
                IngredientEntry.quantity == in_qty,
            )
        ).first()

        if existing_entry is None:
            entry = IngredientEntry(
                ingredient_id=ing.id,
                local_id=local_id,
                quantity=in_qty,
                user_uuid=user_uuid,
                created_at=now,
            )
            session.add(entry)
            session.flush()
            created_movements += 1

            if out_qty > 0:
                exit_rec = IngredientExit(
                    ingredient_id=ing.id,
                    local_id=local_id,
                    quantity=out_qty,
                    user_uuid=user_uuid,
                    created_at=now,
                )
                session.add(exit_rec)
                session.flush()
                created_movements += 1

    session.commit()

    return {
        "ingredients_created": created_ingredients,
        "movements_created": created_movements,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed Brasaland inventory data")
    parser.add_argument(
        "--user",
        required=True,
        help="Email, UUID, or doc_id of a real user in TinyDB",
    )
    args = parser.parse_args()

    backfill_users_uuid()
    init_db()

    engine = get_db_engine()
    with Session(engine) as session:
        result = seed_inventory(session, args.user)
        print(
            f"Seed completed successfully: "
            f"{result['ingredients_created']} ingredients created, "
            f"{result['movements_created']} movements created."
        )


if __name__ == "__main__":
    main()
