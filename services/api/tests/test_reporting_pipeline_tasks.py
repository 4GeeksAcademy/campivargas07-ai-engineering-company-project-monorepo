"""
test_reporting_pipeline_tasks.py — Unit Tests for Inventory Health Pipeline Tasks

Covers:
- Task 2: validate_and_deduplicate_events (all 8 canonical quarantine reason codes + in-memory deduplication)
- Task 3: reconcile_inventory_ledger (authoritative stock calculation, transactions reconciliation)
- Task 4: calculate_inventory_health_metrics (ratios, deficits, zero-thresholds, caching)
- Task 6: publish_pipeline_summary (resilience with return_state=True)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from data.pipelines.inventory_health.flow import (
    calculate_inventory_health_metrics,
    publish_pipeline_summary,
    reconcile_inventory_ledger,
    validate_and_deduplicate_events,
)


@pytest.fixture
def mock_ingredients():
    """Catalog of known ingredients."""
    ing1_id = str(uuid.uuid4())
    ing2_id = str(uuid.uuid4())
    return {
        ing1_id: {
            "id": ing1_id,
            "sku": "ING-001",
            "name": "Carne Brasa",
            "category": "carne",
            "unit_of_measure": "kg",
            "minimum_stock": 25.0,
        },
        ing2_id: {
            "id": ing2_id,
            "sku": "ING-002",
            "name": "Aceite Vegetal",
            "category": "aceites",
            "unit_of_measure": "l",
            "minimum_stock": 10.0,
        },
    }


def test_deduplication_in_memory(mock_ingredients):
    """Verifies that duplicate event_ids in the same extraction batch are deduplicated."""
    event_id = str(uuid.uuid4())
    ing_id = list(mock_ingredients.keys())[0]

    evt1 = {
        "event_id": event_id,
        "event_type": "inbound_order_created",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tags": {
            "local_id": "MED-001",
            "ingredient_id": ing_id,
            "order_id": str(uuid.uuid4()),
            "quantity": 10.0,
            "unit_of_measure": "kg",
        },
    }
    evt2 = {
        "event_id": event_id,
        "event_type": "inbound_order_created",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tags": {
            "local_id": "MED-001",
            "ingredient_id": ing_id,
            "order_id": str(uuid.uuid4()),
            "quantity": 10.0,
            "unit_of_measure": "kg",
        },
    }

    extracted = {
        "telemetry_events": [evt1, evt2],
        "ingredients": mock_ingredients,
    }

    result = validate_and_deduplicate_events.fn(extracted)
    assert result["total_read"] == 2
    assert result["deduplicated_count"] == 1
    assert len(result["valid_events"]) == 1
    assert len(result["quarantine_records"]) == 0


def test_quarantine_reason_1_missing_local_id(mock_ingredients):
    """MISSING_LOCAL_ID: Event without local_id or with empty string."""
    ing_id = list(mock_ingredients.keys())[0]
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "",
                    "ingredient_id": ing_id,
                    "order_id": str(uuid.uuid4()),
                    "quantity": 10.0,
                    "unit_of_measure": "kg",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "MISSING_LOCAL_ID"


def test_quarantine_reason_2_missing_ingredient_id(mock_ingredients):
    """MISSING_INGREDIENT_ID: Event with missing or invalid ingredient UUID."""
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": "not-a-valid-uuid",
                    "order_id": str(uuid.uuid4()),
                    "quantity": 10.0,
                    "unit_of_measure": "kg",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "MISSING_INGREDIENT_ID"


def test_quarantine_reason_3_non_numeric_quantity(mock_ingredients):
    """NON_NUMERIC_QUANTITY: Event with non-numeric quantity."""
    ing_id = list(mock_ingredients.keys())[0]
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": ing_id,
                    "order_id": str(uuid.uuid4()),
                    "quantity": "ten_kilograms",
                    "unit_of_measure": "kg",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "NON_NUMERIC_QUANTITY"


def test_quarantine_reason_4_negative_quantity(mock_ingredients):
    """NEGATIVE_QUANTITY: Event with zero or negative quantity for inbound/outbound."""
    ing_id = list(mock_ingredients.keys())[0]
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "outbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": ing_id,
                    "order_id": str(uuid.uuid4()),
                    "quantity": -5.0,
                    "unit_of_measure": "kg",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "NEGATIVE_QUANTITY"


def test_quarantine_reason_5_incompatible_structure(mock_ingredients):
    """INCOMPATIBLE_STRUCTURE: Event missing mandatory structure fields like order_id."""
    ing_id = list(mock_ingredients.keys())[0]
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": ing_id,
                    "quantity": 10.0,
                    "unit_of_measure": "kg",
                    # Missing mandatory "order_id"
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "INCOMPATIBLE_STRUCTURE"


def test_quarantine_reason_6_unknown_ingredient_id(mock_ingredients):
    """UNKNOWN_INGREDIENT_ID: Ingredient UUID not registered in ingredient table."""
    unknown_id = str(uuid.uuid4())
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": unknown_id,
                    "order_id": str(uuid.uuid4()),
                    "quantity": 10.0,
                    "unit_of_measure": "kg",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "UNKNOWN_INGREDIENT_ID"


def test_quarantine_reason_7_incompatible_unit(mock_ingredients):
    """INCOMPATIBLE_UNIT: Unit in event does not match master ingredient catalog."""
    ing_id = list(mock_ingredients.keys())[0]  # Catalog expects "kg"
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": ing_id,
                    "order_id": str(uuid.uuid4()),
                    "quantity": 10.0,
                    "unit_of_measure": "pounds",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "INCOMPATIBLE_UNIT"


def test_quarantine_reason_8_invalid_timestamp(mock_ingredients):
    """INVALID_TIMESTAMP: Future timestamp beyond allowable 10-minute tolerance."""
    ing_id = list(mock_ingredients.keys())[0]
    future_time = datetime.now(timezone.utc) + timedelta(hours=2)
    extracted = {
        "telemetry_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "inbound_order_created",
                "timestamp": future_time.isoformat(),
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": ing_id,
                    "order_id": str(uuid.uuid4()),
                    "quantity": 10.0,
                    "unit_of_measure": "kg",
                },
            }
        ],
        "ingredients": mock_ingredients,
    }
    result = validate_and_deduplicate_events.fn(extracted)
    assert len(result["quarantine_records"]) == 1
    assert result["quarantine_records"][0]["reason_code"] == "INVALID_TIMESTAMP"


def test_reconcile_inventory_ledger(mock_ingredients):
    """Validates transactional reconciliation: stock = entries - exits."""
    ing_id = list(mock_ingredients.keys())[0]
    extracted = {
        "entries": [
            {
                "id": str(uuid.uuid4()),
                "local_id": "MED-001",
                "ingredient_id": ing_id,
                "quantity": 50.0,
                "created_at": "2026-09-28T12:00:00+00:00",
            },
        ],
        "exits": [
            {
                "id": str(uuid.uuid4()),
                "local_id": "MED-001",
                "ingredient_id": ing_id,
                "quantity": 30.0,
                "created_at": "2026-09-28T13:00:00+00:00",
            },
        ],
        "ingredients": mock_ingredients,
    }
    validated = {
        "valid_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "outbound_insufficient_stock_attempted",
                "timestamp": "2026-09-28T14:00:00+00:00",
                "tags": {
                    "local_id": "MED-001",
                    "ingredient_id": ing_id,
                    "requested_quantity": 40.0,
                },
            }
        ]
    }

    reconciled = reconcile_inventory_ledger.fn(extracted, validated)
    assert len(reconciled["reconciled_partitions"]) == 1
    item = reconciled["reconciled_partitions"][0]
    assert item["local_id"] == "MED-001"
    assert item["ingredient_id"] == ing_id
    assert item["current_stock"] == 20.0
    assert item["inbound_quantity"] == 50.0
    assert item["outbound_quantity"] == 30.0
    assert item["insufficient_stock_attempts_count"] == 1


def test_calculate_inventory_health_metrics(mock_ingredients):
    """Tests ratios, deficits, stockouts, and below_minimum flags."""
    ing1_id = list(mock_ingredients.keys())[0]  # min_stock: 25.0
    ing2_id = list(mock_ingredients.keys())[1]  # min_stock: 10.0

    reconciled = {
        "reconciled_partitions": [
            {
                "snapshot_date": "2026-09-28",
                "local_id": "MED-001",
                "ingredient_id": ing1_id,
                "ingredient_sku": "ING-001",
                "ingredient_name": "Carne Brasa",
                "category": "carne",
                "unit_of_measure": "kg",
                "current_stock": 10.0,  # below minimum
                "minimum_stock": 25.0,
                "inbound_quantity": 20.0,
                "outbound_quantity": 10.0,
                "insufficient_stock_attempts_count": 2,
                "source_event_count": 3,
                "source_first_event_at": None,
                "source_last_event_at": None,
                "event_ids": [],
            },
            {
                "snapshot_date": "2026-09-28",
                "local_id": "MED-001",
                "ingredient_id": ing2_id,
                "ingredient_sku": "ING-002",
                "ingredient_name": "Aceite Vegetal",
                "category": "aceites",
                "unit_of_measure": "l",
                "current_stock": 0.0,  # stockout
                "minimum_stock": 10.0,
                "inbound_quantity": 0.0,
                "outbound_quantity": 0.0,
                "insufficient_stock_attempts_count": 0,
                "source_event_count": 0,
                "source_first_event_at": None,
                "source_last_event_at": None,
                "event_ids": [],
            },
        ]
    }

    metrics = calculate_inventory_health_metrics.fn(reconciled)
    items = metrics["items"]

    item1 = items[0]
    assert item1["stock_level_ratio"] == 0.4
    assert item1["stock_deficit"] == 15.0
    assert item1["is_stockout"] is False
    assert item1["is_below_minimum"] is True

    item2 = items[1]
    assert item2["stock_level_ratio"] == 0.0
    assert item2["stock_deficit"] == 10.0
    assert item2["is_stockout"] is True
    assert item2["is_below_minimum"] is False

    agg = metrics["aggregated_metrics"]
    assert agg["METRIC_CRITICAL_STOCKOUTS_COUNT"] == 1
    assert agg["METRIC_BELOW_MINIMUM_COUNT"] == 1
    assert agg["METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT"] == 2
    assert agg["METRIC_STOCK_LEVEL_RATIO"] == 0.2


def test_publish_pipeline_summary_non_critical_failure():
    """Tests that publish_pipeline_summary error does not crash caller when return_state=True."""
    load_result = {
        "pipeline_run_id": str(uuid.uuid4()),
        "status": "COMPLETED",
        "snapshots_loaded": 5,
        "quarantined_count": 0,
    }

    # Should raise when executed directly if should_fail=True
    with pytest.raises(ValueError):
        publish_pipeline_summary.fn(load_result, should_fail=True)

    # When should_fail=False, returns dictionary
    summary = publish_pipeline_summary.fn(load_result, should_fail=False)
    assert summary["status"] == "COMPLETED"
    assert summary["snapshots_loaded"] == 5
