"""
test_pipeline.py — Brasaland · Isolated Unit Tests for Inventory Health Pipeline

Tests:
1. Validation & Deduplication: Repeated event_id is not counted twice.
2. Defensive Quarantine: Invalid/malformed inputs are quarantined without breaking the batch.
3. Reconciliation & KPI Calculation: Canonical scenario matching PIPELINE_DESIGN.md.
4. Subflow Coordination: transform_inventory_health_data_flow execution & result propagation.
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import Any
from datetime import datetime, timezone

# Ensure monorepo root is on sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from data.pipelines.inventory_health.flow import (
    QUARANTINE_REASONS,
    calculate_inventory_health_metrics,
    reconcile_inventory_ledger,
    transform_inventory_health_data_flow,
    validate_and_deduplicate_events,
)

LOCAL_MED = "MED-001"
ING_RES_ID = "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
ING_POLLO_ID = "4a2ceb3c-2a6c-4cad-8acc-1a0c6a2cba5c"

SAMPLE_CATALOG = {
    ING_RES_ID: {
        "id": ING_RES_ID,
        "sku": "ING-001",
        "name": "Carne de Res Brasa",
        "category": "carne",
        "unit_of_measure": "kg",
        "minimum_stock": 25.0,
        "perishable": True,
    },
    ING_POLLO_ID: {
        "id": ING_POLLO_ID,
        "sku": "ING-002",
        "name": "Pechuga de Pollo",
        "category": "carne",
        "unit_of_measure": "kg",
        "minimum_stock": 20.0,
        "perishable": True,
    },
}


def test_validation_and_deduplication_duplicate_event_id() -> None:
    """
    Test 1: Repeated event_id within a batch is deduplicated and not counted twice.
    """
    duplicate_uuid = str(uuid.uuid4())
    event_timestamp = "2026-09-28T14:00:00+00:00"

    event_payload = {
        "event_id": duplicate_uuid,
        "event_type": "inbound_order_created",
        "timestamp": event_timestamp,
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": ING_RES_ID,
            "quantity": 10.0,
            "unit_of_measure": "kg",
            "resulting_stock": 35.0,
        },
    }

    # Batch with two identical event_ids
    extracted_data = {
        "telemetry_events": [event_payload, event_payload],
        "ingredients": SAMPLE_CATALOG,
        "existing_lineage_event_ids": [],
    }

    result = validate_and_deduplicate_events.fn(extracted_data)

    assert result["total_read"] == 2
    assert result["deduplicated_count"] == 1
    assert len(result["valid_events"]) == 1
    assert len(result["quarantine_records"]) == 0
    assert result["valid_events"][0]["event_id"] == duplicate_uuid


def test_validation_defensive_quarantine_without_breaking_batch() -> None:
    """
    Test 2: Invalid or malformed inputs are quarantined with approved reason codes
    without aborting or corrupting valid events in the batch.
    """
    valid_event_id = str(uuid.uuid4())
    valid_event = {
        "event_id": valid_event_id,
        "event_type": "inbound_order_created",
        "timestamp": "2026-09-28T12:00:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": ING_RES_ID,
            "quantity": 15.0,
            "unit_of_measure": "kg",
        },
    }

    future_timestamp_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "inbound_order_created",
        "timestamp": "2099-01-01T00:00:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": ING_RES_ID,
            "quantity": 10.0,
        },
    }

    missing_local_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "inbound_order_created",
        "timestamp": "2026-09-28T12:01:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": "",  # Missing/empty local_id
            "ingredient_id": ING_RES_ID,
            "quantity": 5.0,
        },
    }

    negative_qty_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "outbound_order_created",
        "timestamp": "2026-09-28T12:02:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": ING_RES_ID,
            "quantity": -4.0,  # Negative quantity
        },
    }

    unknown_ingredient_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "inbound_order_created",
        "timestamp": "2026-09-28T12:03:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": str(uuid.uuid4()),  # Not in SAMPLE_CATALOG
            "quantity": 8.0,
        },
    }

    extracted_data = {
        "telemetry_events": [
            valid_event,
            future_timestamp_event,
            missing_local_event,
            negative_qty_event,
            unknown_ingredient_event,
        ],
        "ingredients": SAMPLE_CATALOG,
        "existing_lineage_event_ids": [],
    }

    result = validate_and_deduplicate_events.fn(extracted_data)

    assert result["total_read"] == 5
    assert len(result["valid_events"]) == 1
    assert result["valid_events"][0]["event_id"] == valid_event_id

    quarantined = result["quarantine_records"]
    assert len(quarantined) == 4

    quarantine_codes = {q["reason_code"] for q in quarantined}
    assert quarantine_codes.issubset(QUARANTINE_REASONS)
    assert "INVALID_TIMESTAMP" in quarantine_codes
    assert "MISSING_LOCAL_ID" in quarantine_codes
    assert "NEGATIVE_QUANTITY" in quarantine_codes
    assert "UNKNOWN_INGREDIENT_ID" in quarantine_codes


def test_reconciliation_and_kpi_calculation_canonical_scenario() -> None:
    """
    Test 3: Reconciliation and KPI calculation matches PIPELINE_DESIGN.md canonical scenario:
    - Ingredient: ING-001 (minimum_stock = 25.0 kg)
    - Inbound entries: 50.0 kg
    - Outbound exits: 35.5 kg
    - Resulting current_stock: 14.5 kg
    - stock_level_ratio: 14.5 / 25.0 = 0.58
    - stock_deficit: 25.0 - 14.5 = 10.5 kg
    - is_stockout: False
    - is_below_minimum: True
    - Insufficient stock attempts: 2
    """
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    extracted_data = {
        "ingredients": SAMPLE_CATALOG,
        "entries": [
            {
                "id": str(uuid.uuid4()),
                "ingredient_id": ING_RES_ID,
                "local_id": LOCAL_MED,
                "quantity": 50.0,
                "created_at": f"{snapshot_date}T08:00:00+00:00",
            }
        ],
        "exits": [
            {
                "id": str(uuid.uuid4()),
                "ingredient_id": ING_RES_ID,
                "local_id": LOCAL_MED,
                "quantity": 35.5,
                "created_at": f"{snapshot_date}T13:00:00+00:00",
            }
        ],
        "affected_partitions": [(LOCAL_MED, ING_RES_ID)],
    }

    # Two insufficient stock attempt telemetry events
    validated_data = {
        "valid_events": [
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "outbound_insufficient_stock_attempted",
                "timestamp": f"{snapshot_date}T14:10:00+00:00",
                "tags": {
                    "local_id": LOCAL_MED,
                    "ingredient_id": ING_RES_ID,
                    "requested_quantity": 5.0,
                    "rejection_source": "client_form_guard",
                },
            },
            {
                "event_id": str(uuid.uuid4()),
                "event_type": "outbound_insufficient_stock_attempted",
                "timestamp": f"{snapshot_date}T14:15:00+00:00",
                "tags": {
                    "local_id": LOCAL_MED,
                    "ingredient_id": ING_RES_ID,
                    "requested_quantity": 8.0,
                    "rejection_source": "backend_transaction_lock",
                },
            },
        ]
    }

    reconciled = reconcile_inventory_ledger.fn(extracted_data, validated_data)
    partitions = reconciled["reconciled_partitions"]
    assert len(partitions) == 1

    part = partitions[0]
    assert part["local_id"] == LOCAL_MED
    assert part["ingredient_id"] == ING_RES_ID
    assert part["current_stock"] == 14.5
    assert part["minimum_stock"] == 25.0
    assert part["inbound_quantity"] == 50.0
    assert part["outbound_quantity"] == 35.5
    assert part["insufficient_stock_attempts_count"] == 2

    # Calculate metrics
    metrics = calculate_inventory_health_metrics.fn(reconciled)
    items = metrics["items"]
    assert len(items) == 1

    item = items[0]
    assert item["stock_level_ratio"] == 0.58
    assert item["stock_deficit"] == 10.5
    assert item["is_stockout"] is False
    assert item["is_below_minimum"] is True
    assert item["insufficient_stock_attempts_count"] == 2

    agg = metrics["aggregated_metrics"]
    assert agg["METRIC_STOCK_LEVEL_RATIO"] == 0.58
    assert agg["METRIC_CRITICAL_STOCKOUTS_COUNT"] == 0
    assert agg["METRIC_BELOW_MINIMUM_COUNT"] == 1
    assert agg["METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT"] == 2


def test_subflow_coordination_and_propagation() -> None:
    """
    Test 4: transform_inventory_health_data_flow executes in sequence and propagates results:
    - Coordinates validation, deduplication, reconciliation, and KPI calculation.
    - Operates purely in-memory without database or external server dependencies.
    """
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    valid_event_id = str(uuid.uuid4())
    dup_event_id = str(uuid.uuid4())

    valid_event = {
        "event_id": valid_event_id,
        "event_type": "inbound_order_created",
        "timestamp": f"{snapshot_date}T10:00:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": ING_POLLO_ID,
            "quantity": 30.0,
            "unit_of_measure": "kg",
        },
    }

    dup_event = {
        "event_id": dup_event_id,
        "event_type": "outbound_order_created",
        "timestamp": f"{snapshot_date}T11:00:00+00:00",
        "tags": {
            "order_id": str(uuid.uuid4()),
            "local_id": LOCAL_MED,
            "ingredient_id": ING_POLLO_ID,
            "quantity": 10.0,
            "unit_of_measure": "kg",
        },
    }

    extracted_data = {
        "telemetry_events": [valid_event, dup_event, dup_event],  # 1 duplicate
        "ingredients": SAMPLE_CATALOG,
        "entries": [
            {
                "id": str(uuid.uuid4()),
                "ingredient_id": ING_POLLO_ID,
                "local_id": LOCAL_MED,
                "quantity": 30.0,
                "created_at": f"{snapshot_date}T10:00:00+00:00",
            }
        ],
        "exits": [
            {
                "id": str(uuid.uuid4()),
                "ingredient_id": ING_POLLO_ID,
                "local_id": LOCAL_MED,
                "quantity": 15.0,
                "created_at": f"{snapshot_date}T12:00:00+00:00",
            }
        ],
        "affected_partitions": [(LOCAL_MED, ING_POLLO_ID)],
        "existing_lineage_event_ids": [],
    }

    # Execute the subflow
    transformed = transform_inventory_health_data_flow(extracted_data)

    assert "validated" in transformed
    assert "reconciled" in transformed
    assert "metrics" in transformed

    # Stage 1: Validation
    validated = transformed["validated"]
    assert validated["total_read"] == 3
    assert validated["deduplicated_count"] == 1
    assert len(validated["valid_events"]) == 2

    # Stage 2: Reconciliation
    reconciled = transformed["reconciled"]
    assert len(reconciled["reconciled_partitions"]) == 1
    part = reconciled["reconciled_partitions"][0]
    assert part["current_stock"] == 15.0  # 30 - 15

    # Stage 3: KPI Metrics
    metrics = transformed["metrics"]
    items = metrics["items"]
    assert len(items) == 1
    item = items[0]
    assert item["current_stock"] == 15.0
    assert item["minimum_stock"] == 20.0
    assert item["stock_level_ratio"] == 0.75  # 15 / 20
    assert item["stock_deficit"] == 5.0
    assert item["is_stockout"] is False
    assert item["is_below_minimum"] is True
