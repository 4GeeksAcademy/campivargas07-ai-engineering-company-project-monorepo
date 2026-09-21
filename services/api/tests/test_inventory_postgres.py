"""
test_inventory_postgres.py — Brasaland · PostgreSQL Integration & Concurrency Tests

Requires: TEST_DATABASE_URL environment variable (e.g. postgresql://postgres:postgres@localhost:5432/brasaland_test_db)
Never touches the production / default Supabase database.
Marked with @pytest.mark.postgres.

Tests:
1. Native PostgreSQL constraints (CHECK quantity > 0, minimum_stock >= 0, FKs).
2. Real concurrency: validates that SELECT ... FOR UPDATE serializes concurrent exits
   so two concurrent requests cannot over-consume available stock.
"""

from __future__ import annotations

import concurrent.futures
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domains.operations.inventory.models import (
    Ingredient,
    IngredientEntry,
    IngredientExit,
)
from app.domains.operations.inventory.repository import (
    InsufficientStockError,
    create_outbound_exit_with_lock,
    get_stock_for_ingredient_and_local,
)

pytestmark = pytest.mark.postgres

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def pg_engine():
    """Provides a dedicated PostgreSQL engine using TEST_DATABASE_URL."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set. Skipping PostgreSQL integration tests.")

    # Create engine and initialize schema
    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)

    from app.database import init_db
    init_db(bind_engine=engine)

    yield engine

    # Teardown: drop test tables
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS ingredient_exit CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS ingredient_entry CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS ingredient CASCADE;"))
        conn.commit()
    engine.dispose()


@pytest.fixture
def pg_session(pg_engine):
    """Provides a transaction-isolated session for PostgreSQL tests."""
    with Session(pg_engine) as session:
        yield session
        session.rollback()


# ────────────────────────────────────────────────────────────
# 1. Native PostgreSQL Constraints
# ────────────────────────────────────────────────────────────

def test_pg_minimum_stock_check_constraint(pg_session: Session):
    """PostgreSQL enforces chk_ingredient_minimum_stock_non_negative."""
    ing = Ingredient(
        sku=f"ING-PG-NEG-{uuid.uuid4().hex[:6]}",
        name="Ingrediente Negativo",
        category="carne",
        unit_of_measure="kg",
        minimum_stock=Decimal("-5.0"),
    )
    pg_session.add(ing)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_pg_entry_quantity_positive_constraint(pg_session: Session):
    """PostgreSQL enforces chk_ingredient_entry_quantity_positive (quantity > 0)."""
    ing = Ingredient(
        sku=f"ING-PG-POS-{uuid.uuid4().hex[:6]}",
        name="Ingrediente Prueba",
        category="verdura",
        unit_of_measure="kg",
        minimum_stock=Decimal("0.0"),
    )
    pg_session.add(ing)
    pg_session.commit()

    entry = IngredientEntry(
        ingredient_id=ing.id,
        local_id="MED-001",
        quantity=Decimal("0.0"),  # Must be strictly > 0
        user_uuid=uuid.uuid4(),
    )
    pg_session.add(entry)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_pg_exit_quantity_positive_constraint(pg_session: Session):
    """PostgreSQL enforces chk_ingredient_exit_quantity_positive (quantity > 0)."""
    ing = Ingredient(
        sku=f"ING-PG-EXIT-{uuid.uuid4().hex[:6]}",
        name="Ingrediente Prueba Exit",
        category="salsa",
        unit_of_measure="litros",
        minimum_stock=Decimal("0.0"),
    )
    pg_session.add(ing)
    pg_session.commit()

    exit_rec = IngredientExit(
        ingredient_id=ing.id,
        local_id="MED-001",
        quantity=Decimal("-2.0"),  # Must be strictly > 0
        user_uuid=uuid.uuid4(),
    )
    pg_session.add(exit_rec)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


def test_pg_foreign_key_constraint(pg_session: Session):
    """PostgreSQL enforces foreign key on ingredient_id."""
    fake_ingredient_id = uuid.uuid4()
    entry = IngredientEntry(
        ingredient_id=fake_ingredient_id,
        local_id="MED-001",
        quantity=Decimal("10.0"),
        user_uuid=uuid.uuid4(),
    )
    pg_session.add(entry)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


# ────────────────────────────────────────────────────────────
# 2. Real Concurrency (Pessimistic Locking / SELECT FOR UPDATE)
# ────────────────────────────────────────────────────────────

def test_pg_concurrent_outbound_movements_prevent_negative_stock(pg_engine):
    """
    Demonstrates pessimistic locking in PostgreSQL under real concurrency:
    - Initial stock: 10.0 units of an ingredient in MED-001.
    - Two concurrent threads each attempt to withdraw 7.0 units.
    - Because 7.0 + 7.0 = 14.0 > 10.0, both cannot succeed.
    - Under SELECT ... FOR UPDATE, one thread must succeed (consuming 7.0, balance 3.0),
      and the other thread must be rejected with InsufficientStockError.
    - Resulting final stock is exactly 3.0 (never negative).
    """
    # 1. Setup ingredient and initial inbound of 10.0
    with Session(pg_engine) as setup_session:
        ing = Ingredient(
            sku=f"ING-CONC-{uuid.uuid4().hex[:6]}",
            name="Carne para Hamburguesa Concurrente",
            category="carne",
            unit_of_measure="kg",
            minimum_stock=Decimal("2.0"),
        )
        setup_session.add(ing)
        setup_session.commit()
        setup_session.refresh(ing)
        ing_id = ing.id

        entry = IngredientEntry(
            ingredient_id=ing_id,
            local_id="MED-001",
            quantity=Decimal("10.0"),
            user_uuid=uuid.uuid4(),
            created_at=datetime.now(timezone.utc),
        )
        setup_session.add(entry)
        setup_session.commit()

    # 2. Define worker function executed concurrently
    def attempt_withdrawal(worker_id: int):
        user_uuid = uuid.uuid4()
        with Session(pg_engine) as session:
            try:
                exit_rec = create_outbound_exit_with_lock(
                    session=session,
                    ingredient_id=ing_id,
                    local_id="MED-001",
                    quantity=Decimal("7.0"),
                    user_uuid=user_uuid,
                )
                return {"success": True, "worker_id": worker_id, "exit_id": exit_rec.id}
            except InsufficientStockError as exc:
                return {"success": False, "worker_id": worker_id, "error": str(exc)}
            except Exception as e:
                return {"success": False, "worker_id": worker_id, "unexpected": str(e)}

    # 3. Run two concurrent withdrawals
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(attempt_withdrawal, 1)
        f2 = executor.submit(attempt_withdrawal, 2)
        r1 = f1.result()
        r2 = f2.result()

    results = [r1, r2]
    successes = [r for r in results if r["success"]]
    failures = [r for r in results if not r["success"]]

    # Exactly ONE withdrawal must succeed and ONE must fail
    assert len(successes) == 1, f"Expected exactly 1 success, got: {results}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got: {results}"
    assert "Insufficient stock" in failures[0]["error"]

    # 4. Final verification: remaining stock is strictly 3.0
    with Session(pg_engine) as verify_session:
        final_stock = get_stock_for_ingredient_and_local(verify_session, ing_id, "MED-001")
        assert final_stock == Decimal("3.0"), f"Expected stock 3.0, got: {final_stock}"

        # Verify only 1 exit record exists
        exits = verify_session.exec(
            select(IngredientExit).where(
                IngredientExit.ingredient_id == ing_id,
                IngredientExit.local_id == "MED-001",
            )
        ).all()
        assert len(exits) == 1
        assert exits[0].quantity == Decimal("7.0")

