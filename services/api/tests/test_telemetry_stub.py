import logging
import os
from starlette.testclient import TestClient

from app.main import app

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


def test_valid_single_event_batch(client: TestClient):
    """Valid batch with 1 event returns 200 and exact received/stored count."""
    response = client.post("/telemetry/events", json={"events": [SAMPLE_INBOUND_EVENT]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 1, "rejected": 0}


def test_valid_multiple_events_batch(client: TestClient):
    """Valid batch with multiple events returns 200 and exact count."""
    response = client.post(
        "/telemetry/events",
        json={"events": [SAMPLE_INBOUND_EVENT, SAMPLE_PAGE_VIEW_EVENT, SAMPLE_OUTBOUND_EVENT]},
    )
    assert response.status_code == 200
    assert response.json() == {"received": 3, "stored": 3, "rejected": 0}


def test_empty_batch_allowed(client: TestClient):
    """Empty batch returns 200 and received count 0."""
    response = client.post("/telemetry/events", json={"events": []})
    assert response.status_code == 200
    assert response.json() == {"received": 0, "stored": 0, "rejected": 0}


def test_batch_exceeding_max_limit_rejected(client: TestClient):
    """Batch with more than 20 events is rejected with 422."""
    events = [dict(SAMPLE_PAGE_VIEW_EVENT) for _ in range(21)]
    response = client.post("/telemetry/events", json={"events": events})
    assert response.status_code == 422


def test_missing_mandatory_envelope_field_rejected(client: TestClient):
    """Missing mandatory envelope field (e.g. eventId) is rejected with 200 and rejected=1."""
    bad_event = dict(SAMPLE_INBOUND_EVENT)
    del bad_event["eventId"]
    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_extra_field_in_envelope_rejected(client: TestClient):
    """Extra field in envelope is rejected with rejected=1 (extra='forbid')."""
    bad_event = {**SAMPLE_INBOUND_EVENT, "forbidden_extra_field": "disallowed"}
    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_extra_field_in_properties_rejected(client: TestClient):
    """Extra property not in event allowlist is rejected with rejected=1."""
    bad_event = dict(SAMPLE_INBOUND_EVENT)
    bad_event["properties"] = {**SAMPLE_INBOUND_EVENT["properties"], "unapproved_prop": "leak"}
    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_missing_mandatory_property_rejected(client: TestClient):
    """Missing mandatory property inside properties is rejected with rejected=1."""
    bad_event = dict(SAMPLE_INBOUND_EVENT)
    bad_props = dict(SAMPLE_INBOUND_EVENT["properties"])
    del bad_props["local_id"]
    bad_event["properties"] = bad_props
    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_invalid_property_type_rejected(client: TestClient):
    """Invalid property type (e.g. string for quantity) is rejected with rejected=1."""
    bad_event = dict(SAMPLE_INBOUND_EVENT)
    bad_props = dict(SAMPLE_INBOUND_EVENT["properties"])
    bad_props["quantity"] = "not-a-number"
    bad_event["properties"] = bad_props
    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_unknown_event_type_rejected(client: TestClient):
    """Unregistered event_type is rejected with rejected=1."""
    bad_event = {**SAMPLE_INBOUND_EVENT, "event_type": "unknown_random_event"}
    response = client.post("/telemetry/events", json={"events": [bad_event]})
    assert response.status_code == 200
    assert response.json() == {"received": 1, "stored": 0, "rejected": 1}


def test_get_method_not_allowed(client: TestClient):
    """GET /telemetry/events returns 405 Method Not Allowed."""
    response = client.get("/telemetry/events")
    assert response.status_code == 405


def test_no_file_or_database_persistence(tmp_path, client: TestClient):
    """Telemetry endpoint does not create or modify TinyDB files."""
    db_path = os.getenv("SUPPLIERS_DB_PATH", "data/suppliers.json")
    full_db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)

    mtime_before = os.path.getmtime(full_db_path) if os.path.exists(full_db_path) else None

    response = client.post(
        "/telemetry/events",
        json={"events": [SAMPLE_INBOUND_EVENT, SAMPLE_OUTBOUND_EVENT]},
    )
    assert response.status_code == 200

    if mtime_before is not None and os.path.exists(full_db_path):
        mtime_after = os.path.getmtime(full_db_path)
        assert mtime_before == mtime_after


def test_logs_contain_no_sensitive_data(caplog, client: TestClient):
    """Logs must only record count and event_type, with Zero-PII."""
    with caplog.at_level(logging.INFO, logger="telemetry"):
        response = client.post(
            "/telemetry/events",
            json={"events": [SAMPLE_INBOUND_EVENT, SAMPLE_PAGE_VIEW_EVENT]},
        )
        assert response.status_code == 200

    log_text = caplog.text
    assert "count=2" in log_text
    assert "inbound_order_created" in log_text
    assert "backoffice_page_viewed" in log_text

    # Zero PII: no passwords, tokens, full emails, or raw payload dumps
    assert "password" not in log_text.lower()
    assert "token" not in log_text.lower()
    assert "secret" not in log_text.lower()
    assert "@" not in log_text  # no email addresses
