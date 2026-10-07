"""
test_reporting_pipeline_flow.py — PostgreSQL Integration Tests for Inventory Health Flow

Validates:
1. End-to-end execution of inventory_health_business_flow on real PostgreSQL tables.
2. Idempotency: Second run produces identical snapshot rows and does not fail on lineage.
3. Concurrency: Advisory lock skipping when another execution is active.
4. Rollback: Failure before commit leaves no partial data in snapshots and does not advance checkpoint.
5. CLI Entrypoint: Direct invocation of pipeline.py main() returns exit code 0.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from data.pipelines.inventory_health.flow import (
    PIPELINE_ADVISORY_LOCK_ID,
    inventory_health_business_flow,
)

pytestmark = pytest.mark.postgres
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def pg_flow_engine():
    """Provides a PostgreSQL engine initialized with both telemetry and reporting migrations."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not configured. Skipping PostgreSQL pipeline integration tests.")

    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)

    # Apply 001_create_telemetry_events.sql
    mig1_path = Path(__file__).resolve().parent.parent / "migrations" / "001_create_telemetry_events.sql"
    with engine.connect() as conn:
        conn.execute(text(mig1_path.read_text(encoding="utf-8")))
        conn.commit()

    # Apply 002_create_inventory_health_reporting.sql
    mig2_path = Path(__file__).resolve().parent.parent / "migrations" / "002_create_inventory_health_reporting.sql"
    with engine.connect() as conn:
        conn.execute(text(mig2_path.read_text(encoding="utf-8")))
        conn.commit()

    # Ensure ingredient catalog and transactional tables exist using canonical SQLModel schema
    from app.database import init_db
    init_db(bind_engine=engine)

    yield engine

    engine.dispose()


@pytest.fixture(autouse=True)
def clean_reporting_tables(pg_flow_engine):
    """Truncates reporting and staging data between test runs for deterministic assertions."""
    with pg_flow_engine.begin() as conn:
        conn.execute(text("TRUNCATE reporting.inventory_health_lineage CASCADE;"))
        conn.execute(text("TRUNCATE reporting.inventory_health_quarantine CASCADE;"))
        conn.execute(text("TRUNCATE reporting.inventory_health_snapshot CASCADE;"))
        conn.execute(text("TRUNCATE reporting.pipeline_checkpoints CASCADE;"))
        conn.execute(text("TRUNCATE reporting.pipeline_execution_logs CASCADE;"))
        conn.execute(text("TRUNCATE ingredient_entry CASCADE;"))
        conn.execute(text("TRUNCATE ingredient_exit CASCADE;"))
        conn.execute(text("TRUNCATE telemetry_events CASCADE;"))
        conn.execute(text("DELETE FROM ingredient;"))


def test_pipeline_end_to_end_and_idempotency(pg_flow_engine):
    """
    Validates end-to-end execution and idempotency:
    - First run processes seed data, computes snapshot, populates lineage and checkpoints.
    - Second run executes identically via UPSERT without duplicate key errors.
    """
    ing_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    # 1. Seed catalog and ledger
    with pg_flow_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO ingredient (id, sku, name, category, unit_of_measure, minimum_stock, perishable, created_at) "
                "VALUES (:id, 'ING-FLOW-01', 'Pechuga Brasa', 'carne', 'kg', 20.0, true, :created_at)"
            ),
            {"id": ing_id, "created_at": now_utc},
        )
        conn.execute(
            text(
                "INSERT INTO ingredient_entry (id, ingredient_id, local_id, quantity, user_uuid, created_at) "
                "VALUES (:id, :ing_id, 'MED-001', 50.0, :user_uuid, :created_at)"
            ),
            {"id": uuid.uuid4(), "ing_id": ing_id, "user_uuid": uuid.uuid4(), "created_at": now_utc},
        )
        conn.execute(
            text(
                "INSERT INTO ingredient_exit (id, ingredient_id, local_id, quantity, user_uuid, created_at) "
                "VALUES (:id, :ing_id, 'MED-001', 35.0, :user_uuid, :created_at)"
            ),
            {"id": uuid.uuid4(), "ing_id": ing_id, "user_uuid": uuid.uuid4(), "created_at": now_utc},
        )

    # 2. First Run
    result1 = inventory_health_business_flow(
        db_url=TEST_DB_URL,
        is_full_reconciliation=True,
    )
    assert result1["status"] == "COMPLETED"
    assert result1["snapshots_loaded"] >= 1

    with pg_flow_engine.connect() as conn:
        snapshot_count_1 = conn.execute(
            text("SELECT COUNT(*) FROM reporting.inventory_health_snapshot")
        ).scalar()
        assert snapshot_count_1 >= 1

        snap_row = conn.execute(
            text("SELECT current_stock, minimum_stock, is_below_minimum FROM reporting.inventory_health_snapshot WHERE ingredient_id = :id"),
            {"id": ing_id},
        ).fetchone()
        assert snap_row is not None
        assert float(snap_row[0]) == 15.0  # 50 - 35
        assert float(snap_row[1]) == 20.0
        assert snap_row[2] is True  # Below minimum!

    # 3. Second Run (Idempotency verification)
    result2 = inventory_health_business_flow(
        db_url=TEST_DB_URL,
        is_full_reconciliation=True,
    )
    assert result2["status"] == "COMPLETED"

    with pg_flow_engine.connect() as conn:
        snapshot_count_2 = conn.execute(
            text("SELECT COUNT(*) FROM reporting.inventory_health_snapshot")
        ).scalar()
        assert snapshot_count_2 == snapshot_count_1  # No duplicate rows created!


def test_pipeline_concurrency_lock_skips(pg_flow_engine):
    """
    Validates concurrency control:
    If another process holds the PostgreSQL advisory lock, the flow immediately returns SKIPPED.
    """
    with pg_flow_engine.connect() as lock_conn:
        # Acquire advisory lock in separate connection
        lock_conn.execute(text(f"SELECT pg_advisory_lock({PIPELINE_ADVISORY_LOCK_ID})"))

        try:
            result = inventory_health_business_flow(db_url=TEST_DB_URL)
            assert result["status"] == "SKIPPED"
            assert "concurrency lock" in result["message"]
        finally:
            lock_conn.execute(text(f"SELECT pg_advisory_unlock({PIPELINE_ADVISORY_LOCK_ID})"))


def test_cli_entrypoint_execution(pg_flow_engine):
    """
    Verifies that data/pipelines/pipeline.py can be invoked via CLI and returns exit code 0.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    cli_path = repo_root / "data" / "pipelines" / "pipeline.py"

    env = dict(os.environ)
    env["DATABASE_URL"] = TEST_DB_URL

    proc = subprocess.run(
        [sys.executable, str(cli_path), "--full-reconciliation"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )

    assert proc.returncode == 0
    assert "BRASALAND INVENTORY HEALTH PIPELINE — RUN SUMMARY" in proc.stdout
    assert "Status:              COMPLETED" in proc.stdout


def test_transactional_rollback_on_failure(pg_flow_engine):
    """
    Validates transactional atomicity and rollback:
    If a failure occurs during snapshot loading before commit,
    all changes are rolled back, leaving 0 rows in snapshot and unadvanced checkpoints.
    """
    from unittest.mock import patch
    from data.pipelines.inventory_health.flow import load_inventory_health_snapshot

    ing_id = str(uuid.uuid4())
    metrics_data = {
        "items": [
            {
                "snapshot_date": "2026-09-28",
                "local_id": "MED-001",
                "ingredient_id": ing_id,
                "ingredient_sku": "ING-ROLLBACK-01",
                "ingredient_name": "Ingrediente Test Rollback",
                "category": "verduras",
                "unit_of_measure": "kg",
                "current_stock": 25.0,
                "minimum_stock": 10.0,
                "stock_level_ratio": 2.5,
                "stock_deficit": 0.0,
                "is_stockout": False,
                "is_below_minimum": False,
                "inbound_quantity": 25.0,
                "outbound_quantity": 0.0,
                "insufficient_stock_attempts_count": 0,
                "source_event_count": 1,
                "source_first_event_at": None,
                "source_last_event_at": None,
                "event_ids": [str(uuid.uuid4())],
            }
        ]
    }
    validated_data = {
        "quarantine_records": [
            {
                "quarantine_id": str(uuid.uuid4()),
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "reason_code": "MISSING_LOCAL_ID",
                "reason_detail": "Testing rollback",
                "raw_payload": {"test": "data"},
            }
        ]
    }
    extracted_data = {
        "watermark_timestamp": "2026-09-28T10:00:00+00:00",
        "watermark_event_id": str(uuid.uuid4()),
        "telemetry_events": [],
    }

    # Simulate write failure in json.dumps when saving quarantine
    with patch("data.pipelines.inventory_health.flow.json.dumps", side_effect=RuntimeError("Simulated write failure")):
        with pytest.raises(RuntimeError, match="Simulated write failure"):
            load_inventory_health_snapshot.fn(
                metrics_data=metrics_data,
                validated_data=validated_data,
                extracted_data=extracted_data,
                pipeline_run_id=str(uuid.uuid4()),
                db_url=TEST_DB_URL,
            )

    # Verify atomic rollback: no partial snapshots or checkpoints exist
    with pg_flow_engine.connect() as conn:
        snapshots_count = conn.execute(
            text("SELECT COUNT(*) FROM reporting.inventory_health_snapshot WHERE ingredient_id = :id"),
            {"id": uuid.UUID(ing_id)},
        ).scalar()
        assert snapshots_count == 0

        checkpoints_count = conn.execute(
            text("SELECT COUNT(*) FROM reporting.pipeline_checkpoints")
        ).scalar()
        assert checkpoints_count == 0

