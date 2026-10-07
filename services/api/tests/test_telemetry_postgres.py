"""
test_telemetry_postgres.py — PostgreSQL Integration Tests for Telemetry Events Storage

Requires: TEST_DATABASE_URL environment variable (e.g. postgresql://postgres:postgres@localhost:5432/brasaland_api_test)
Marked with @pytest.mark.postgres.

Validates:
1. Native PostgreSQL DDL execution (001_create_telemetry_events.sql) and 8 exact columns.
2. 3 explicit indexes in PostgreSQL: timestamp, event_type, and GIN index on tags (JSONB).
3. Real bulk insert and JSONB querying in PostgreSQL.
4. Idempotent deduplication via ON CONFLICT (event_id) DO NOTHING.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.domains.telemetry.models import TelemetryEventRecord
from app.domains.telemetry.repository import bulk_insert_telemetry_events

pytestmark = pytest.mark.postgres

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def pg_engine():
    """Provides a dedicated PostgreSQL engine using TEST_DATABASE_URL."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not set. Skipping PostgreSQL integration tests.")

    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)

    # Execute migration script directly to test raw DDL idempotency
    migration_path = Path(__file__).resolve().parent.parent / "migrations" / "001_create_telemetry_events.sql"
    migration_sql = migration_path.read_text(encoding="utf-8")

    with engine.connect() as conn:
        conn.execute(text(migration_sql))
        conn.commit()

    yield engine

    # Cleanup teardown
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS telemetry_events CASCADE;"))
        conn.commit()
    engine.dispose()


def test_postgres_table_schema_and_eight_columns(pg_engine):
    """Validates that telemetry_events has exactly eight columns with correct Postgres types."""
    with pg_engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'telemetry_events'
            ORDER BY ordinal_position;
        """)).fetchall()

    columns_dict = {r[0]: (r[1], r[2]) for r in rows}
    assert len(columns_dict) == 8, f"Expected exactly 8 columns, got {len(columns_dict)}"

    # Exact column specifications
    assert columns_dict["event_id"][1] == "uuid"
    assert columns_dict["event_type"][0] == "character varying"
    assert columns_dict["timestamp"][0] == "timestamp with time zone"
    assert columns_dict["service"][0] == "character varying"
    assert columns_dict["session_id"][0] == "character varying"
    assert columns_dict["user_id"][1] == "uuid"
    assert columns_dict["request_id"][0] == "character varying"
    assert columns_dict["tags"][1] == "jsonb"


def test_postgres_three_explicit_indexes(pg_engine):
    """Validates that the 3 required explicit indexes exist in PostgreSQL."""
    with pg_engine.connect() as conn:
        indices = conn.execute(text("""
            SELECT indexname, indexdef 
            FROM pg_indexes 
            WHERE tablename = 'telemetry_events';
        """)).fetchall()

    index_names = {r[0] for r in indices}
    index_defs = {r[0]: r[1] for r in indices}

    # 1. Primary key index on event_id
    assert "telemetry_events_pkey" in index_names

    # 2. Index on timestamp
    assert "idx_telemetry_events_timestamp" in index_names
    assert "timestamp" in index_defs["idx_telemetry_events_timestamp"]

    # 3. Index on event_type
    assert "idx_telemetry_events_event_type" in index_names
    assert "event_type" in index_defs["idx_telemetry_events_event_type"]

    # 4. GIN index on tags
    assert "idx_telemetry_events_tags_gin" in index_names
    assert "USING gin" in index_defs["idx_telemetry_events_tags_gin"]
    assert "tags" in index_defs["idx_telemetry_events_tags_gin"]


def test_postgres_real_bulk_insert_and_jsonb_query(pg_engine):
    """Tests real PostgreSQL bulk insert and JSONB querying capabilities."""
    with Session(pg_engine) as session:
        event_1_id = uuid.uuid4()
        event_2_id = uuid.uuid4()
        rows = [
            {
                "event_id": event_1_id,
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc),
                "service": "backoffice",
                "session_id": "sess-1",
                "user_id": uuid.uuid4(),
                "request_id": "req-1",
                "tags": {"local_id": "MED-001", "quantity": 10.5, "unit_of_measure": "kg"},
            },
            {
                "event_id": event_2_id,
                "event_type": "outbound_order_created",
                "timestamp": datetime.now(timezone.utc),
                "service": "backoffice",
                "session_id": "sess-1",
                "user_id": uuid.uuid4(),
                "request_id": "req-2",
                "tags": {"local_id": "MIA-001", "quantity": 4.0, "unit_of_measure": "kg"},
            },
        ]
        inserted = bulk_insert_telemetry_events(session, rows)
        session.commit()
        assert inserted == 2

    # Query using native PostgreSQL JSONB operator
    with pg_engine.connect() as conn:
        res = conn.execute(text("""
            SELECT event_id, event_type, tags->>'local_id' as local_id, (tags->>'quantity')::numeric as qty
            FROM telemetry_events
            WHERE tags @> '{"local_id": "MED-001"}'::jsonb;
        """)).fetchall()
        assert len(res) == 1
        assert res[0][1] == "inbound_order_created"
        assert res[0][2] == "MED-001"
        assert float(res[0][3]) == 10.5


def test_postgres_duplicate_prevention_on_conflict(pg_engine):
    """Verifies that re-inserting the same event_id does not duplicate rows."""
    event_id = uuid.uuid4()
    row = {
        "event_id": event_id,
        "event_type": "backoffice_page_viewed",
        "timestamp": datetime.now(timezone.utc),
        "service": "backoffice",
        "session_id": None,
        "user_id": None,
        "request_id": "req-3",
        "tags": {"current_route": "/backoffice/overview"},
    }

    with Session(pg_engine) as session:
        # First insertion: 1 inserted
        inserted_first = bulk_insert_telemetry_events(session, [row])
        session.commit()
        assert inserted_first == 1

        # Second insertion with same event_id: 0 inserted
        inserted_second = bulk_insert_telemetry_events(session, [row])
        session.commit()
        assert inserted_second == 0

    with pg_engine.connect() as conn:
        count = conn.execute(
            text("SELECT count(*) FROM telemetry_events WHERE event_id = :eid;"),
            {"eid": event_id},
        ).scalar()
        assert count == 1

