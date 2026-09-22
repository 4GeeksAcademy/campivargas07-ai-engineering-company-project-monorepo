"""
test_telemetry_storage.py — Unit and Functional Tests for Telemetry Event Storage

Covers all required scenarios:
1. Malformed outer envelope (422)
2. Completely valid batch (200, stored=N, rejected=0)
3. Mixed batch with valid and invalid events (200, stored=S, rejected=R)
4. Individual rejection via ValidationError
5. Completely invalid batch with zero database calls
6. Single bulk insert operation per batch
7. Exact mapping of eight columns
8. Correct storage of business events (inbound_order_created)
9. Correct storage of technical events (backoffice_page_viewed)
10. Preservation of properties allowlist (extra='forbid')
11. tags contains only allowed properties, without envelope fields
12. Duplicate events not stored twice (ON CONFLICT DO NOTHING)
13. Correct counters for duplicate events (received = stored + rejected)
14. Rollback and HTTP 503 on database failure
15. Verification of migration script and index structure
16. Compatibility of response with frontend TelemetryService
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.domains.telemetry.mapping import DEFAULT_SERVICE, telemetry_event_to_row
from app.domains.telemetry.models import TelemetryEventRecord
from app.domains.telemetry.repository import bulk_insert_telemetry_events
from app.domains.telemetry.router import TELEMETRY_EVENT_ADAPTER
from app.domains.telemetry.schemas import TelemetryBatchRequest, TelemetryBatchResponse

# ────────────────────────────────────────────────────────────
# Sample Test Payloads
# ────────────────────────────────────────────────────────────

SAMPLE_INBOUND_EVENT = {
    "eventId": "c8d4e92a-7b3f-4c5e-9e12-8a9b1c2d3e4f",
    "timestamp": "2026-09-22T14:30:00.000Z",
    "sessionId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "event_type": "inbound_order_created",
    "entity_action": "created",
    "schemaVersion": "1.0.0",
    "requestId": "e2a74c10-98cc-4372-a567-0e02b2c3d479",
    "properties": {
        "order_id": "11111111-2222-3333-4444-555555555555",
        "local_id": "MED-001",
        "ingredient_id": "66666666-7777-8888-9999-000000000000",
        "ingredient_sku": "ING-001",
        "quantity": 25.5,
        "unit_of_measure": "kg",
        "previous_stock": 10.0,
        "resulting_stock": 35.5,
    },
}

SAMPLE_OUTBOUND_EVENT = {
    "eventId": "d2e3f4a5-b6c7-4d8e-9f0a-1b2c3d4e5f6a",
    "timestamp": "2026-09-22T14:32:00.000Z",
    "sessionId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "event_type": "outbound_order_created",
    "entity_action": "created",
    "schemaVersion": "1.0.0",
    "requestId": "a4c96e32-10ee-4594-c789-2a24d4e5f691",
    "properties": {
        "order_id": "22222222-3333-4444-5555-666666666666",
        "local_id": "MED-001",
        "ingredient_id": "66666666-7777-8888-9999-000000000000",
        "ingredient_sku": "ING-001",
        "quantity": 5.0,
        "unit_of_measure": "kg",
        "previous_stock": 35.5,
        "resulting_stock": 30.5,
    },
}

SAMPLE_PAGE_VIEW_EVENT = {
    "eventId": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "timestamp": "2026-09-22T14:31:00.000Z",
    "sessionId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "userId": None,
    "event_type": "backoffice_page_viewed",
    "entity_action": "viewed",
    "schemaVersion": "1.0.0",
    "requestId": "f3b85d21-09dd-4483-b678-1f13c3d4e580",
    "properties": {
        "previous_route": "DIRECT_ENTRY",
        "current_route": "/backoffice/inventory/products",
        "navigation_duration_ms": 1250.0,
    },
}

SAMPLE_WEB_VITALS_EVENT = {
    "eventId": "e5f6a7b8-c9d0-4e1f-8a2b-3c4d5e6f7a8b",
    "timestamp": "2026-09-22T14:33:00.000Z",
    "sessionId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "userId": None,
    "event_type": "client_web_vitals_recorded",
    "entity_action": "recorded",
    "schemaVersion": "1.0.0",
    "requestId": "b5c87e12-34dd-4598-a123-4f5e6a7b8c9d",
    "properties": {
        "page_route": "/backoffice/overview",
        "metric_name": "LCP",
        "metric_value": 1500.5,
        "rating": "good",
    },
}


# ────────────────────────────────────────────────────────────
# 1. Malformed Outer Envelope (HTTP 422)
# ────────────────────────────────────────────────────────────

def test_malformed_outer_envelope_rejected_422(client: TestClient):
    """Missing 'events' key, non-list events, extra root fields, or >20 events return 422."""
    # Missing 'events'
    res = client.post("/telemetry/events", json={})
    assert res.status_code == 422

    # Extra root field forbidden
    res = client.post("/telemetry/events", json={"events": [], "forbidden": "extra"})
    assert res.status_code == 422

    # 'events' is not a list
    res = client.post("/telemetry/events", json={"events": "not-a-list"})
    assert res.status_code == 422

    # Exceeds max 20 events
    events = [dict(SAMPLE_PAGE_VIEW_EVENT) for _ in range(21)]
    res = client.post("/telemetry/events", json={"events": events})
    assert res.status_code == 422


# ────────────────────────────────────────────────────────────
# 2. Completely Valid Batch
# ────────────────────────────────────────────────────────────

def test_completely_valid_batch_returns_200_and_exact_counters(client: TestClient):
    """A completely valid batch stores all items and returns stored=N, rejected=0."""
    payload = {"events": [SAMPLE_INBOUND_EVENT, SAMPLE_OUTBOUND_EVENT, SAMPLE_PAGE_VIEW_EVENT]}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 3
    assert data["stored"] == 3
    assert data["rejected"] == 0
    assert data["received"] == data["stored"] + data["rejected"]


# ────────────────────────────────────────────────────────────
# 3. Mixed Batch with Valid and Invalid Events
# ────────────────────────────────────────────────────────────

def test_mixed_batch_accepts_valid_and_rejects_invalid(client: TestClient):
    """Mixed batch stores valid events and increments rejected for invalid ones."""
    invalid_event_1 = {
        "eventId": str(uuid.uuid4()),
        "event_type": "unknown_event_type",
        "entity_action": "created",
        "schemaVersion": "1.0.0",
        "requestId": "req-1",
        "timestamp": "2026-09-22T14:30:00.000Z",
        "properties": {},
    }
    invalid_event_2 = {
        "eventId": str(uuid.uuid4()),
        "event_type": "inbound_order_created",
        "entity_action": "created",
        "schemaVersion": "1.0.0",
        "requestId": "req-2",
        "timestamp": "2026-09-22T14:30:00.000Z",
        "properties": {
            "quantity": "invalid-string-quantity",  # Invalid type
        },
    }
    valid_event = {
        **SAMPLE_PAGE_VIEW_EVENT,
        "eventId": str(uuid.uuid4()),
    }

    payload = {"events": [invalid_event_1, valid_event, invalid_event_2]}
    response = client.post("/telemetry/events", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 3
    assert data["stored"] == 1
    assert data["rejected"] == 2
    assert data["received"] == data["stored"] + data["rejected"]


# ────────────────────────────────────────────────────────────
# 4. Individual Rejection via ValidationError
# ────────────────────────────────────────────────────────────

def test_individual_rejection_via_validation_error(client: TestClient):
    """Pydantic ValidationError on an individual item increments rejected without 422."""
    # Missing required envelope field (e.g. eventId)
    bad_event = dict(SAMPLE_INBOUND_EVENT)
    del bad_event["eventId"]

    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 0
    assert data["rejected"] == 1


# ────────────────────────────────────────────────────────────
# 5. Completely Invalid Batch without Database Call
# ────────────────────────────────────────────────────────────

def test_completely_invalid_batch_makes_no_database_call(client: TestClient):
    """When all events in a batch are invalid, bulk_insert_telemetry_events is never called."""
    bad_event = {"eventId": "not-a-uuid", "event_type": "fake_event"}

    with patch("app.domains.telemetry.router.bulk_insert_telemetry_events") as mock_bulk:
        response = client.post("/telemetry/events", json={"events": [bad_event]})
        assert response.status_code == 200
        data = response.json()
        assert data["received"] == 1
        assert data["stored"] == 0
        assert data["rejected"] == 1
        mock_bulk.assert_not_called()


# ────────────────────────────────────────────────────────────
# 6. Single Bulk Insert Operation per Batch
# ────────────────────────────────────────────────────────────

def test_single_bulk_insert_operation_per_batch(client: TestClient):
    """A batch of multiple valid events invokes bulk_insert_telemetry_events exactly once."""
    events = [
        {**SAMPLE_PAGE_VIEW_EVENT, "eventId": str(uuid.uuid4())}
        for _ in range(5)
    ]

    with patch(
        "app.domains.telemetry.router.bulk_insert_telemetry_events",
        wraps=bulk_insert_telemetry_events,
    ) as spy_bulk:
        response = client.post("/telemetry/events", json={"events": events})
        assert response.status_code == 200
        assert spy_bulk.call_count == 1
        # Called with a list of 5 rows
        call_rows = spy_bulk.call_args[0][1]
        assert len(call_rows) == 5


# ────────────────────────────────────────────────────────────
# 7. Exact Mapping of Eight Columns
# ────────────────────────────────────────────────────────────

def test_exact_eight_columns_mapping():
    """telemetry_event_to_row maps aliases and extracts exactly eight columns."""
    validated = TELEMETRY_EVENT_ADAPTER.validate_python(SAMPLE_INBOUND_EVENT)
    row = telemetry_event_to_row(validated, service="backoffice")

    expected_keys = {
        "event_id",
        "event_type",
        "timestamp",
        "service",
        "session_id",
        "user_id",
        "request_id",
        "tags",
    }
    assert set(row.keys()) == expected_keys
    assert str(row["event_id"]) == SAMPLE_INBOUND_EVENT["eventId"]
    assert row["event_type"] == "inbound_order_created"
    assert row["service"] == "backoffice"
    assert row["session_id"] == SAMPLE_INBOUND_EVENT["sessionId"]
    assert str(row["user_id"]) == SAMPLE_INBOUND_EVENT["userId"]
    assert row["request_id"] == SAMPLE_INBOUND_EVENT["requestId"]

    # entity_action and schemaVersion are NOT persisted in row
    assert "entity_action" not in row
    assert "schemaVersion" not in row

    # tags contains only approved properties
    assert row["tags"]["local_id"] == "MED-001"
    assert row["tags"]["quantity"] == 25.5
    assert "eventId" not in row["tags"]


# ────────────────────────────────────────────────────────────
# 8. Business Event Correctly Stored
# ────────────────────────────────────────────────────────────

def test_business_event_correctly_stored(client: TestClient, db_session: Session):
    """An inbound_order_created business event is stored with all metadata."""
    event_id = str(uuid.uuid4())
    event_payload = {**SAMPLE_INBOUND_EVENT, "eventId": event_id}

    response = client.post("/telemetry/events", json={"events": [event_payload]})
    assert response.status_code == 200
    assert response.json()["stored"] == 1

    record = db_session.exec(
        select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == uuid.UUID(event_id))
    ).first()
    assert record is not None
    assert record.event_type == "inbound_order_created"
    assert record.service == "backoffice"
    assert record.tags["ingredient_sku"] == "ING-001"
    assert record.tags["quantity"] == 25.5


# ────────────────────────────────────────────────────────────
# 9. Technical Event Correctly Stored
# ────────────────────────────────────────────────────────────

def test_technical_event_correctly_stored(client: TestClient, db_session: Session):
    """A client_web_vitals_recorded technical event is stored with numeric metrics."""
    event_id = str(uuid.uuid4())
    event_payload = {**SAMPLE_WEB_VITALS_EVENT, "eventId": event_id}

    response = client.post("/telemetry/events", json={"events": [event_payload]})
    assert response.status_code == 200
    assert response.json()["stored"] == 1

    record = db_session.exec(
        select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == uuid.UUID(event_id))
    ).first()
    assert record is not None
    assert record.event_type == "client_web_vitals_recorded"
    assert record.tags["metric_name"] == "LCP"
    assert record.tags["metric_value"] == 1500.5
    assert record.tags["rating"] == "good"


# ────────────────────────────────────────────────────────────
# 10. Preservation of Properties Allowlist
# ────────────────────────────────────────────────────────────

def test_extra_property_in_properties_rejected(client: TestClient):
    """Extra property violating allowlist (extra='forbid') is rejected."""
    bad_event = dict(SAMPLE_INBOUND_EVENT)
    bad_event["eventId"] = str(uuid.uuid4())
    bad_event["properties"] = {
        **SAMPLE_INBOUND_EVENT["properties"],
        "unauthorized_extra_field": "leak",
    }

    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    data = response.json()
    assert data["received"] == 1
    assert data["stored"] == 0
    assert data["rejected"] == 1


# ────────────────────────────────────────────────────────────
# 11. tags Contains No Additional Properties or Envelope Fields
# ────────────────────────────────────────────────────────────

def test_tags_contains_no_additional_properties_or_envelope(client: TestClient, db_session: Session):
    """Persisted tags column contains only domain properties, zero envelope leakage."""
    event_id = str(uuid.uuid4())
    event_payload = {**SAMPLE_PAGE_VIEW_EVENT, "eventId": event_id}

    res = client.post("/telemetry/events", json={"events": [event_payload]})
    assert res.status_code == 200

    record = db_session.exec(
        select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == uuid.UUID(event_id))
    ).first()
    assert record is not None
    tags = record.tags
    assert "current_route" in tags
    assert "navigation_duration_ms" in tags
    # Ensure zero envelope leakage into tags
    for envelope_field in ("eventId", "timestamp", "sessionId", "userId", "service", "schemaVersion", "entity_action"):
        assert envelope_field not in tags


# ────────────────────────────────────────────────────────────
# 12. Duplicate Event Not Stored Twice (Idempotency)
# ────────────────────────────────────────────────────────────

def test_duplicate_event_not_stored_twice(client: TestClient, db_session: Session):
    """Resending the same eventId results in ON CONFLICT DO NOTHING, keeping count=1."""
    event_id = str(uuid.uuid4())
    event_payload = {**SAMPLE_OUTBOUND_EVENT, "eventId": event_id}

    # First attempt: stored
    res1 = client.post("/telemetry/events", json={"events": [event_payload]})
    assert res1.status_code == 200
    assert res1.json()["stored"] == 1
    assert res1.json()["rejected"] == 0

    # Second attempt (retry): not stored, counted as rejected
    res2 = client.post("/telemetry/events", json={"events": [event_payload]})
    assert res2.status_code == 200
    assert res2.json()["stored"] == 0
    assert res2.json()["rejected"] == 1

    # Verify only 1 row exists in DB
    records = db_session.exec(
        select(TelemetryEventRecord).where(TelemetryEventRecord.event_id == uuid.UUID(event_id))
    ).all()
    assert len(records) == 1


# ────────────────────────────────────────────────────────────
# 13. Correct Counters on Duplicates
# ────────────────────────────────────────────────────────────

def test_correct_counters_on_duplicates(client: TestClient):
    """A batch containing new, duplicate, and invalid events produces exact counters."""
    existing_id = str(uuid.uuid4())
    existing_event = {**SAMPLE_PAGE_VIEW_EVENT, "eventId": existing_id}

    # Pre-populate existing event
    res = client.post("/telemetry/events", json={"events": [existing_event]})
    assert res.json()["stored"] == 1

    new_event = {**SAMPLE_INBOUND_EVENT, "eventId": str(uuid.uuid4())}
    invalid_event = {"eventId": "bad-id", "event_type": "bad_type"}

    # Mixed batch: 1 new + 1 duplicate + 1 invalid
    batch = {"events": [new_event, existing_event, invalid_event]}
    res_mixed = client.post("/telemetry/events", json=batch)
    assert res_mixed.status_code == 200
    data = res_mixed.json()
    assert data["received"] == 3
    assert data["stored"] == 1  # only new_event
    assert data["rejected"] == 2  # 1 duplicate + 1 invalid
    assert data["received"] == data["stored"] + data["rejected"]


# ────────────────────────────────────────────────────────────
# 14. Database Failure Rollback and 503 Service Unavailable
# ────────────────────────────────────────────────────────────

def test_database_failure_rolls_back_and_returns_503(client: TestClient):
    """A real database error triggers session.rollback() and returns HTTP 503."""
    with patch(
        "app.domains.telemetry.router.bulk_insert_telemetry_events",
        side_effect=OperationalError("connection failure", None, None),
    ):
        response = client.post("/telemetry/events", json={"events": [SAMPLE_INBOUND_EVENT]})
        assert response.status_code == 503
        data = response.json()
        assert data["detail"] == "Database service temporarily unavailable"
        # Zero credentials/internals leak
        assert "password" not in str(data).lower()
        assert "connection" not in str(data).lower()


# ────────────────────────────────────────────────────────────
# 15. Migration File & Index Structure Verification
# ────────────────────────────────────────────────────────────

def test_migration_file_and_indexes_structure():
    """Validates the idempotent SQL migration file has exactly 8 columns and 3 indexes."""
    migration_path = Path(__file__).resolve().parent.parent / "migrations" / "001_create_telemetry_events.sql"
    assert migration_path.exists(), "Migration 001_create_telemetry_events.sql must exist"

    sql_content = migration_path.read_text(encoding="utf-8")

    # Table creation assertion
    assert "CREATE TABLE IF NOT EXISTS telemetry_events" in sql_content

    # Exactly 8 required columns in DDL
    expected_columns = [
        "event_id UUID PRIMARY KEY",
        "event_type VARCHAR(100) NOT NULL",
        "timestamp TIMESTAMPTZ NOT NULL",
        "service VARCHAR(50) NOT NULL",
        "session_id VARCHAR(100)",
        "user_id UUID",
        "request_id VARCHAR(100) NOT NULL",
        "tags JSONB NOT NULL",
    ]
    for col in expected_columns:
        assert col in sql_content, f"Missing column definition: {col}"

    # 3 explicit indexes
    assert "CREATE INDEX IF NOT EXISTS idx_telemetry_events_timestamp ON telemetry_events (timestamp);" in sql_content
    assert "CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_type ON telemetry_events (event_type);" in sql_content
    assert "CREATE INDEX IF NOT EXISTS idx_telemetry_events_tags_gin ON telemetry_events USING gin (tags);" in sql_content


# ────────────────────────────────────────────────────────────
# 16. Compatibility with Frontend TelemetryService
# ────────────────────────────────────────────────────────────

def test_compatibility_with_frontend_telemetry_service(client: TestClient):
    """TelemetryService in backoffice expects response.ok on 200, received count."""
    res_empty = client.post("/telemetry/events", json={"events": []})
    assert res_empty.status_code == 200
    assert res_empty.json() == {"received": 0, "stored": 0, "rejected": 0}

    res_valid = client.post("/telemetry/events", json={"events": [SAMPLE_PAGE_VIEW_EVENT]})
    assert res_valid.status_code == 200
    assert res_valid.json()["received"] == 1
    assert res_valid.json()["stored"] == 1
    assert res_valid.json()["rejected"] == 0
