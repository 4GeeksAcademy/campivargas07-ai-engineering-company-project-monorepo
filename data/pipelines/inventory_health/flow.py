"""
flow.py — Brasaland · Inventory Health Business Performance Pipeline (Prefect 3)

Implements the resilient, idempotent inventory health business pipeline:
- Flow: inventory_health_business_flow
- Tasks:
  1. extract_inventory_changes (retries=3, [30, 60, 120]s for transient PostgreSQL timeouts)
  2. validate_and_deduplicate_events (retries=0, pure validation, quarantine routing)
  3. reconcile_inventory_ledger (retries=3, [10, 30, 60]s for transient PostgreSQL read drops)
  4. calculate_inventory_health_metrics (retries=0, pure transformation with Prefect cache & TTL)
  5. load_inventory_health_snapshot (retries=3, [15, 30, 60]s for transient PostgreSQL write contention)
  6. publish_pipeline_summary (secondary non-critical task invoked with return_state=True)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from prefect import flow, task
from prefect.tasks import task_input_hash
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from data.pipelines.inventory_health.queries import (
    get_pipeline_run_status,
    record_execution_start,
)

__all__ = [
    "inventory_health_business_flow",
    "extract_inventory_health_data_flow",
    "transform_inventory_health_data_flow",
    "load_inventory_health_snapshot_flow",
    "trigger_inventory_health_flow",
    "get_pipeline_run_status",
    "extract_inventory_changes",
    "validate_and_deduplicate_events",
    "reconcile_inventory_ledger",
    "calculate_inventory_health_metrics",
    "load_inventory_health_snapshot",
    "publish_pipeline_summary",
    "PIPELINE_ADVISORY_LOCK_ID",
    "QUARANTINE_REASONS",
]

logger = logging.getLogger("inventory_health_pipeline")

# Advisory lock identifier for pipeline concurrency control
PIPELINE_ADVISORY_LOCK_ID = 84920491

# Canonical quarantine reason codes approved in PIPELINE_DESIGN.md
QUARANTINE_REASONS = {
    "MISSING_LOCAL_ID",
    "MISSING_INGREDIENT_ID",
    "NON_NUMERIC_QUANTITY",
    "NEGATIVE_QUANTITY",
    "INCOMPATIBLE_STRUCTURE",
    "UNKNOWN_INGREDIENT_ID",
    "INCOMPATIBLE_UNIT",
    "INVALID_TIMESTAMP",
}


def _get_engine(db_url: Optional[str] = None) -> Engine:
    """Returns an active SQLAlchemy engine for database operations."""
    resolved_url = db_url or os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not resolved_url:
        raise RuntimeError("DATABASE_URL or TEST_DATABASE_URL must be configured.")
    return create_engine(resolved_url, pool_pre_ping=True)


def _check_schema_exists(conn) -> None:
    """Verifies that the reporting schema and tables exist before running."""
    schema_exists = conn.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'reporting'")
    ).scalar()
    if not schema_exists:
        raise RuntimeError(
            "Required schema 'reporting' does not exist in the database. "
            "Please apply migration 'services/api/migrations/002_create_inventory_health_reporting.sql' before running the pipeline."
        )

    table_exists = conn.execute(
        text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'reporting' AND table_name = 'inventory_health_snapshot'")
    ).scalar()
    if not table_exists:
        raise RuntimeError(
            "Required table 'reporting.inventory_health_snapshot' does not exist. "
            "Please apply migration 'services/api/migrations/002_create_inventory_health_reporting.sql' before running the pipeline."
        )


# ==============================================================================
# Task 1: Extract Inventory Changes
# ==============================================================================
# Retries configured to handle transient PostgreSQL connection/read timeouts or temporary pool exhaustion
@task(
    name="extract_inventory_changes",
    retries=3,
    retry_delay_seconds=[30, 60, 120],
)
def extract_inventory_changes(
    db_url: Optional[str] = None,
    is_full_reconciliation: bool = False,
) -> dict[str, Any]:
    """
    Extracts telemetry events (read-only) and transactional kardex entries.
    Respects checkpoints and rolling 48-hour window.
    """
    engine = _get_engine(db_url)
    with engine.connect() as conn:
        _check_schema_exists(conn)

        # 1. Fetch current checkpoint watermark
        checkpoint_row = conn.execute(
            text(
                "SELECT watermark_timestamp, watermark_event_id "
                "FROM reporting.pipeline_checkpoints "
                "WHERE pipeline_name = 'inventory_health_business' AND source_name = 'telemetry_events'"
            )
        ).fetchone()

        watermark_ts = checkpoint_row[0] if checkpoint_row else None
        watermark_evt_id = str(checkpoint_row[1]) if checkpoint_row and checkpoint_row[1] else None

        # 2. Determine rolling 48h extraction window
        now_utc = datetime.now(timezone.utc)
        if watermark_ts:
            if watermark_ts.tzinfo is None:
                watermark_ts = watermark_ts.replace(tzinfo=timezone.utc)
            window_start = watermark_ts - timedelta(hours=48)
        else:
            # First execution: read all available events from the beginning
            window_start = datetime(2000, 1, 1, tzinfo=timezone.utc)

        # 3. Read telemetry_events (read-only: event_id, timestamp, event_type, tags)
        telemetry_stmt = text(
            "SELECT event_id, timestamp, event_type, tags "
            "FROM telemetry_events "
            "WHERE event_type IN ("
            "    'inbound_order_created',"
            "    'outbound_order_created',"
            "    'stock_threshold_triggered',"
            "    'outbound_insufficient_stock_attempted'"
            ") "
            "AND timestamp >= :window_start "
            "ORDER BY timestamp ASC, event_id ASC"
        )
        raw_events = conn.execute(telemetry_stmt, {"window_start": window_start}).fetchall()

        events_data = []
        affected_partitions = set()
        for row in raw_events:
            e_id, ts, e_type, tags = row
            tags_dict = tags if isinstance(tags, dict) else (json.loads(tags) if isinstance(tags, str) else {})
            events_data.append(
                {
                    "event_id": str(e_id),
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "event_type": str(e_type),
                    "tags": tags_dict,
                }
            )
            loc = tags_dict.get("local_id")
            ing = tags_dict.get("ingredient_id")
            if loc and ing:
                affected_partitions.add((str(loc), str(ing)))

        # 4. Check for active partitions from ingredient_entry and ingredient_exit in the window
        kardex_partitions_stmt = text(
            "SELECT DISTINCT local_id, ingredient_id FROM ingredient_entry WHERE created_at >= :window_start "
            "UNION "
            "SELECT DISTINCT local_id, ingredient_id FROM ingredient_exit WHERE created_at >= :window_start"
        )
        kardex_parts = conn.execute(kardex_partitions_stmt, {"window_start": window_start}).fetchall()
        for p in kardex_parts:
            affected_partitions.add((str(p[0]), str(p[1])))

        if is_full_reconciliation or not affected_partitions:
            all_parts_stmt = text(
                "SELECT DISTINCT local_id, ingredient_id FROM ingredient_entry "
                "UNION "
                "SELECT DISTINCT local_id, ingredient_id FROM ingredient_exit"
            )
            for p in conn.execute(all_parts_stmt).fetchall():
                affected_partitions.add((str(p[0]), str(p[1])))

        # 5. Extract ingredient catalog
        ingredients_stmt = text(
            "SELECT id, sku, name, category, unit_of_measure, minimum_stock, perishable "
            "FROM ingredient"
        )
        ing_rows = conn.execute(ingredients_stmt).fetchall()
        ingredients_map = {}
        for ing in ing_rows:
            ingredients_map[str(ing[0])] = {
                "id": str(ing[0]),
                "sku": str(ing[1]),
                "name": str(ing[2]),
                "category": str(ing[3]),
                "unit_of_measure": str(ing[4]),
                "minimum_stock": float(ing[5]),
                "perishable": bool(ing[6]),
            }

        # 6. Extract entries and exits
        entries_stmt = text(
            "SELECT id, ingredient_id, local_id, quantity, created_at "
            "FROM ingredient_entry ORDER BY created_at ASC"
        )
        raw_entries = conn.execute(entries_stmt).fetchall()
        entries_data = [
            {
                "id": str(r[0]),
                "ingredient_id": str(r[1]),
                "local_id": str(r[2]),
                "quantity": float(r[3]),
                "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            }
            for r in raw_entries
        ]

        exits_stmt = text(
            "SELECT id, ingredient_id, local_id, quantity, created_at "
            "FROM ingredient_exit ORDER BY created_at ASC"
        )
        raw_exits = conn.execute(exits_stmt).fetchall()
        exits_data = [
            {
                "id": str(r[0]),
                "ingredient_id": str(r[1]),
                "local_id": str(r[2]),
                "quantity": float(r[3]),
                "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
            }
            for r in raw_exits
        ]

        # 7. Existing lineage for deduplication / late detection
        lineage_event_ids = set()
        if events_data:
            lineage_rows = conn.execute(
                text("SELECT event_id FROM reporting.inventory_health_lineage")
            ).fetchall()
            lineage_event_ids = {str(r[0]) for r in lineage_rows}

        return {
            "telemetry_events": events_data,
            "ingredients": ingredients_map,
            "entries": entries_data,
            "exits": exits_data,
            "affected_partitions": list(affected_partitions),
            "existing_lineage_event_ids": list(lineage_event_ids),
            "watermark_timestamp": watermark_ts.isoformat() if watermark_ts else None,
            "watermark_event_id": watermark_evt_id,
            "window_start": window_start.isoformat(),
            "extracted_at": now_utc.isoformat(),
        }


# ==============================================================================
# Task 2: Validate and Deduplicate Events
# ==============================================================================
@task(
    name="validate_and_deduplicate_events",
    retries=0,  # Pure task; deterministic data validation errors are quarantined without retries
)
def validate_and_deduplicate_events(extracted_data: dict[str, Any]) -> dict[str, Any]:
    """
    Validates event structure according to event_type.
    Deduplicates events by event_id within the batch.
    Routes invalid events to quarantine with approved reason codes.
    Does NOT store sensitive credentials or tokens in raw_payload.
    """
    raw_events = extracted_data.get("telemetry_events", [])
    catalog_ingredients = extracted_data.get("ingredients", {})
    existing_lineage = set(extracted_data.get("existing_lineage_event_ids", []))

    valid_events = []
    quarantine_records = []
    seen_in_batch = set()
    deduplicated_count = 0
    now_utc = datetime.now(timezone.utc)

    for evt in raw_events:
        event_id = evt.get("event_id")
        event_type = evt.get("event_type")
        timestamp_str = evt.get("timestamp")
        tags = evt.get("tags") or {}

        # Deduplication in batch
        if event_id in seen_in_batch:
            deduplicated_count += 1
            continue
        seen_in_batch.add(event_id)

        # 1. Validate Timestamp
        try:
            ts = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            if ts > now_utc + timedelta(minutes=10):
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "INVALID_TIMESTAMP",
                        f"Timestamp {timestamp_str} is in the future beyond acceptable tolerance.",
                        evt,
                    )
                )
                continue
        except Exception:
            quarantine_records.append(
                _create_quarantine_record(
                    event_id,
                    event_type,
                    "INVALID_TIMESTAMP",
                    f"Timestamp '{timestamp_str}' cannot be parsed as valid ISO 8601.",
                    evt,
                )
            )
            continue

        # 2. Validate local_id
        local_id = tags.get("local_id")
        if not local_id or not isinstance(local_id, str) or not local_id.strip():
            quarantine_records.append(
                _create_quarantine_record(
                    event_id,
                    event_type,
                    "MISSING_LOCAL_ID",
                    "Missing or empty 'local_id' in tags.",
                    evt,
                )
            )
            continue

        # 3. Validate ingredient_id
        ing_id = tags.get("ingredient_id")
        if not ing_id:
            quarantine_records.append(
                _create_quarantine_record(
                    event_id,
                    event_type,
                    "MISSING_INGREDIENT_ID",
                    "Missing 'ingredient_id' in tags.",
                    evt,
                )
            )
            continue
        try:
            UUID(str(ing_id))
        except ValueError:
            quarantine_records.append(
                _create_quarantine_record(
                    event_id,
                    event_type,
                    "MISSING_INGREDIENT_ID",
                    f"Invalid UUID for ingredient_id: '{ing_id}'.",
                    evt,
                )
            )
            continue

        # 4. Validate ingredient exists in catalog
        catalog_item = catalog_ingredients.get(str(ing_id))
        if not catalog_item:
            quarantine_records.append(
                _create_quarantine_record(
                    event_id,
                    event_type,
                    "UNKNOWN_INGREDIENT_ID",
                    f"Ingredient ID '{ing_id}' does not exist in ingredient catalog.",
                    evt,
                )
            )
            continue

        # 5. Validate unit_of_measure compatibility
        unit = tags.get("unit_of_measure")
        if unit and unit != catalog_item.get("unit_of_measure"):
            quarantine_records.append(
                _create_quarantine_record(
                    event_id,
                    event_type,
                    "INCOMPATIBLE_UNIT",
                    f"Unit '{unit}' does not match catalog unit '{catalog_item.get('unit_of_measure')}'.",
                    evt,
                )
            )
            continue

        # 6. Event-specific quantity & structural validations
        if event_type in ("inbound_order_created", "outbound_order_created"):
            qty = tags.get("quantity")
            if qty is None:
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "NON_NUMERIC_QUANTITY",
                        "Missing quantity in order movement event.",
                        evt,
                    )
                )
                continue
            try:
                qty_float = float(qty)
            except (ValueError, TypeError):
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "NON_NUMERIC_QUANTITY",
                        f"Quantity '{qty}' is not a valid number.",
                        evt,
                    )
                )
                continue

            if qty_float <= 0:
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "NEGATIVE_QUANTITY",
                        f"Quantity {qty_float} must be strictly positive (> 0).",
                        evt,
                    )
                )
                continue

            if not tags.get("order_id"):
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "INCOMPATIBLE_STRUCTURE",
                        "Missing 'order_id' for inventory order event.",
                        evt,
                    )
                )
                continue

        elif event_type == "outbound_insufficient_stock_attempted":
            req_qty = tags.get("requested_quantity")
            if req_qty is None:
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "NON_NUMERIC_QUANTITY",
                        "Missing requested_quantity in insufficient stock attempt.",
                        evt,
                    )
                )
                continue
            try:
                req_qty_float = float(req_qty)
            except (ValueError, TypeError):
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "NON_NUMERIC_QUANTITY",
                        f"Requested quantity '{req_qty}' is not a valid number.",
                        evt,
                    )
                )
                continue

            if req_qty_float <= 0:
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "NEGATIVE_QUANTITY",
                        f"Requested quantity {req_qty_float} must be strictly positive.",
                        evt,
                    )
                )
                continue

            rejection_src = tags.get("rejection_source")
            if rejection_src not in ("client_form_guard", "backend_transaction_lock"):
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "INCOMPATIBLE_STRUCTURE",
                        f"Invalid rejection_source: '{rejection_src}'.",
                        evt,
                    )
                )
                continue

        elif event_type == "stock_threshold_triggered":
            if "current_stock" not in tags or "minimum_stock" not in tags:
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "INCOMPATIBLE_STRUCTURE",
                        "Missing current_stock or minimum_stock in stock_threshold_triggered event.",
                        evt,
                    )
                )
                continue
            sev = tags.get("severity")
            if sev not in ("critical_depletion", "minimum_reached"):
                quarantine_records.append(
                    _create_quarantine_record(
                        event_id,
                        event_type,
                        "INCOMPATIBLE_STRUCTURE",
                        f"Invalid severity value: '{sev}'.",
                        evt,
                    )
                )
                continue

        # Event is valid!
        valid_events.append(evt)

    return {
        "valid_events": valid_events,
        "quarantine_records": quarantine_records,
        "deduplicated_count": deduplicated_count,
        "total_read": len(raw_events),
    }


def _create_quarantine_record(
    event_id: Any,
    event_type: Any,
    reason_code: str,
    reason_detail: str,
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    """Builds a Zero-PII quarantine record dict."""
    safe_payload = {
        "event_id": str(event_id) if event_id else None,
        "event_type": str(event_type) if event_type else None,
        "timestamp": raw_event.get("timestamp"),
        "tags": raw_event.get("tags") or {},
    }
    return {
        "quarantine_id": str(uuid.uuid4()),
        "event_id": str(event_id) if event_id else None,
        "event_type": str(event_type or "unknown"),
        "reason_code": reason_code,
        "reason_detail": reason_detail,
        "raw_payload": safe_payload,
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
    }


# ==============================================================================
# Task 3: Reconcile Inventory Ledger
# ==============================================================================
# Retries configured to handle transient PostgreSQL connection drops during transactional ledger reads
@task(
    name="reconcile_inventory_ledger",
    retries=3,
    retry_delay_seconds=[10, 30, 60],
)
def reconcile_inventory_ledger(
    extracted_data: dict[str, Any],
    validated_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Computes authoritative current stock:
        current_stock = SUM(ingredient_entry.quantity) - SUM(ingredient_exit.quantity)
    Reconciles with telemetry events per partition (snapshot_date, local_id, ingredient_id).
    Tracks ledger_without_telemetry and telemetry_without_ledger for observability.
    """
    ingredients = extracted_data.get("ingredients", {})
    entries = extracted_data.get("entries", [])
    exits = extracted_data.get("exits", [])
    valid_events = validated_data.get("valid_events", [])
    affected_partitions = set(tuple(p) for p in extracted_data.get("affected_partitions", []))

    # Pre-aggregate all cumulative entries and exits per (local_id, ingredient_id)
    cumulative_stock: dict[tuple[str, str], float] = {}
    for entry in entries:
        key = (entry["local_id"], entry["ingredient_id"])
        cumulative_stock[key] = cumulative_stock.get(key, 0.0) + entry["quantity"]
    for exit_ in exits:
        key = (exit_["local_id"], exit_["ingredient_id"])
        cumulative_stock[key] = cumulative_stock.get(key, 0.0) - exit_["quantity"]

    # Gather dates affected from entries, exits, and valid events
    partition_dates: dict[tuple[str, str, str], dict[str, Any]] = {}

    def _ensure_slot(d_str: str, loc: str, ing: str):
        k = (d_str, loc, ing)
        if k not in partition_dates:
            partition_dates[k] = {
                "snapshot_date": d_str,
                "local_id": loc,
                "ingredient_id": ing,
                "inbound_quantity": 0.0,
                "outbound_quantity": 0.0,
                "insufficient_stock_attempts_count": 0,
                "events": [],
                "entries_on_date": set(),
                "exits_on_date": set(),
            }
        return partition_dates[k]

    # Map entries by date
    for entry in entries:
        d = entry["created_at"][:10]
        slot = _ensure_slot(d, entry["local_id"], entry["ingredient_id"])
        slot["inbound_quantity"] += entry["quantity"]
        slot["entries_on_date"].add(entry["id"])

    # Map exits by date
    for exit_ in exits:
        d = exit_["created_at"][:10]
        slot = _ensure_slot(d, exit_["local_id"], exit_["ingredient_id"])
        slot["outbound_quantity"] += exit_["quantity"]
        slot["exits_on_date"].add(exit_["id"])

    # Map valid telemetry events
    for evt in valid_events:
        d = evt["timestamp"][:10]
        tags = evt.get("tags") or {}
        loc = tags.get("local_id")
        ing = tags.get("ingredient_id")
        if loc and ing:
            slot = _ensure_slot(d, loc, ing)
            slot["events"].append(evt)
            if evt["event_type"] == "outbound_insufficient_stock_attempted":
                slot["insufficient_stock_attempts_count"] += 1

    # Ensure all affected partitions have at least today's slot if active
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for loc, ing in affected_partitions:
        _ensure_slot(today_str, loc, ing)

    # Reconcile each partition-date combination
    reconciled_rows = []
    ledger_without_telemetry = 0
    telemetry_without_ledger = 0
    stock_discrepancies = 0

    for (d_str, loc, ing), data in partition_dates.items():
        ing_meta = ingredients.get(ing, {})
        auth_current_stock = round(cumulative_stock.get((loc, ing), 0.0), 2)
        min_stock = float(ing_meta.get("minimum_stock", 0.0))

        events = data["events"]
        source_count = len(events)
        source_first_at = None
        source_last_at = None
        if events:
            sorted_events = sorted(events, key=lambda x: x["timestamp"])
            source_first_at = sorted_events[0]["timestamp"]
            source_last_at = sorted_events[-1]["timestamp"]

            # Discrepancy check against resulting_stock of latest order event
            order_evts = [e for e in sorted_events if e["event_type"] in ("inbound_order_created", "outbound_order_created")]
            if order_evts:
                last_resulting = order_evts[-1].get("tags", {}).get("resulting_stock")
                if last_resulting is not None and abs(float(last_resulting) - auth_current_stock) > 0.01:
                    stock_discrepancies += 1

        # Check order_ids correlation
        telemetry_order_ids = {
            e.get("tags", {}).get("order_id")
            for e in events
            if e.get("tags", {}).get("order_id")
        }
        all_kardex_ids = data["entries_on_date"] | data["exits_on_date"]

        for kid in all_kardex_ids:
            if kid not in telemetry_order_ids:
                ledger_without_telemetry += 1
        for tid in telemetry_order_ids:
            if tid not in all_kardex_ids:
                telemetry_without_ledger += 1

        reconciled_rows.append(
            {
                "snapshot_date": d_str,
                "local_id": loc,
                "ingredient_id": ing,
                "ingredient_sku": ing_meta.get("sku", "UNKNOWN"),
                "ingredient_name": ing_meta.get("name", "Unknown Ingredient"),
                "category": ing_meta.get("category", "carne"),
                "unit_of_measure": ing_meta.get("unit_of_measure", "unidades"),
                "current_stock": auth_current_stock,
                "minimum_stock": min_stock,
                "inbound_quantity": round(data["inbound_quantity"], 2),
                "outbound_quantity": round(data["outbound_quantity"], 2),
                "insufficient_stock_attempts_count": data["insufficient_stock_attempts_count"],
                "source_event_count": source_count,
                "source_first_event_at": source_first_at,
                "source_last_event_at": source_last_at,
                "event_ids": [e["event_id"] for e in events],
            }
        )

    # Sort deterministically
    reconciled_rows.sort(key=lambda r: (r["snapshot_date"], r["local_id"], r["ingredient_id"]))

    return {
        "reconciled_partitions": reconciled_rows,
        "observability": {
            "ledger_without_telemetry_count": ledger_without_telemetry,
            "telemetry_without_ledger_count": telemetry_without_ledger,
            "stock_discrepancies_count": stock_discrepancies,
        },
    }


# ==============================================================================
# Task 4: Calculate Inventory Health Metrics (Cached)
# ==============================================================================
@task(
    name="calculate_inventory_health_metrics",
    cache_key_fn=task_input_hash,
    cache_expiration=timedelta(minutes=15),
    retries=0,  # Pure task; deterministic KPI calculations do not require retries
)
def calculate_inventory_health_metrics(reconciled_data: dict[str, Any]) -> dict[str, Any]:
    """
    Computes approved KPIs:
    - stock_level_ratio = current_stock / minimum_stock (null if min=0)
    - stock_deficit = max(minimum_stock - current_stock, 0)
    - is_stockout = current_stock <= 0
    - is_below_minimum = current_stock > 0 and current_stock <= minimum_stock
    - Aggregated METRIC_* counters
    """
    partitions = reconciled_data.get("reconciled_partitions", [])
    computed_items = []

    critical_stockouts = 0
    below_minimum_count = 0
    total_insufficient_attempts = 0
    valid_ratios = []

    for item in partitions:
        cur_stock = item["current_stock"]
        min_stock = item["minimum_stock"]

        # Stock level ratio calculation
        if min_stock > 0:
            ratio = round(cur_stock / min_stock, 4)
            valid_ratios.append(ratio)
        else:
            ratio = None
            logger.warning(
                "Quality warning: minimum_stock is 0 for ingredient %s in local %s. Ratio set to null.",
                item["ingredient_id"],
                item["local_id"],
            )

        # Stock deficit calculation
        deficit = round(max(min_stock - cur_stock, 0.0), 2)

        # Boolean flags
        is_stockout = bool(cur_stock <= 0)
        is_below_min = bool(cur_stock > 0 and cur_stock <= min_stock)

        if is_stockout:
            critical_stockouts += 1
        if is_below_min:
            below_minimum_count += 1

        attempts = item.get("insufficient_stock_attempts_count", 0)
        total_insufficient_attempts += attempts

        computed = dict(item)
        computed["stock_level_ratio"] = ratio
        computed["stock_deficit"] = deficit
        computed["is_stockout"] = is_stockout
        computed["is_below_minimum"] = is_below_min
        computed_items.append(computed)

    avg_ratio = round(sum(valid_ratios) / len(valid_ratios), 4) if valid_ratios else None

    return {
        "items": computed_items,
        "aggregated_metrics": {
            "METRIC_STOCK_LEVEL_RATIO": avg_ratio,
            "METRIC_CRITICAL_STOCKOUTS_COUNT": critical_stockouts,
            "METRIC_BELOW_MINIMUM_COUNT": below_minimum_count,
            "METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT": total_insufficient_attempts,
        },
    }


# ==============================================================================
# Task 5: Load Inventory Health Snapshot (Idempotent Transaction)
# ==============================================================================
# Retries configured to handle transient PostgreSQL write lock contention or brief network blips during atomic commit
@task(
    name="load_inventory_health_snapshot",
    retries=3,
    retry_delay_seconds=[15, 30, 60],
)
def load_inventory_health_snapshot(
    metrics_data: dict[str, Any],
    validated_data: dict[str, Any],
    extracted_data: dict[str, Any],
    pipeline_run_id: str,
    db_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Executes atomic idempotent loading inside a single transaction:
    1. UPSERT into reporting.inventory_health_snapshot
    2. INSERT into reporting.inventory_health_lineage
    3. INSERT into reporting.inventory_health_quarantine
    4. UPDATE checkpoint in reporting.pipeline_checkpoints
    5. UPDATE execution log in reporting.pipeline_execution_logs to COMPLETED
    """
    engine = _get_engine(db_url)
    items = metrics_data.get("items", [])
    quarantine_records = validated_data.get("quarantine_records", [])
    valid_events = validated_data.get("valid_events", [])
    now_utc = datetime.now(timezone.utc)

    # Determine latest watermark from valid events processed
    latest_event_ts = None
    latest_event_id = None
    for evt in valid_events:
        ts_val = evt["timestamp"]
        ts_obj = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
        if latest_event_ts is None or ts_obj > latest_event_ts:
            latest_event_ts = ts_obj
            latest_event_id = evt["event_id"]

    # Fallback to previous watermark if no new events
    if latest_event_ts is None and extracted_data.get("watermark_timestamp"):
        latest_event_ts = datetime.fromisoformat(extracted_data["watermark_timestamp"].replace("Z", "+00:00"))
        latest_event_id = extracted_data.get("watermark_event_id")

    with engine.begin() as conn:
        _check_schema_exists(conn)

        # 1. UPSERT snapshots
        snapshot_upsert_stmt = text(
            "INSERT INTO reporting.inventory_health_snapshot ("
            "    snapshot_date, local_id, ingredient_id, ingredient_sku, ingredient_name, "
            "    category, unit_of_measure, current_stock, minimum_stock, stock_level_ratio, "
            "    stock_deficit, is_stockout, is_below_minimum, inbound_quantity, outbound_quantity, "
            "    insufficient_stock_attempts_count, source_event_count, source_first_event_at, "
            "    source_last_event_at, pipeline_run_id, computed_at"
            ") VALUES ("
            "    :snapshot_date, :local_id, :ingredient_id, :ingredient_sku, :ingredient_name, "
            "    :category, :unit_of_measure, :current_stock, :minimum_stock, :stock_level_ratio, "
            "    :stock_deficit, :is_stockout, :is_below_minimum, :inbound_quantity, :outbound_quantity, "
            "    :insufficient_stock_attempts_count, :source_event_count, :source_first_event_at, "
            "    :source_last_event_at, :pipeline_run_id, :computed_at"
            ") ON CONFLICT (snapshot_date, local_id, ingredient_id) DO UPDATE SET "
            "    ingredient_sku = EXCLUDED.ingredient_sku, "
            "    ingredient_name = EXCLUDED.ingredient_name, "
            "    category = EXCLUDED.category, "
            "    unit_of_measure = EXCLUDED.unit_of_measure, "
            "    current_stock = EXCLUDED.current_stock, "
            "    minimum_stock = EXCLUDED.minimum_stock, "
            "    stock_level_ratio = EXCLUDED.stock_level_ratio, "
            "    stock_deficit = EXCLUDED.stock_deficit, "
            "    is_stockout = EXCLUDED.is_stockout, "
            "    is_below_minimum = EXCLUDED.is_below_minimum, "
            "    inbound_quantity = EXCLUDED.inbound_quantity, "
            "    outbound_quantity = EXCLUDED.outbound_quantity, "
            "    insufficient_stock_attempts_count = EXCLUDED.insufficient_stock_attempts_count, "
            "    source_event_count = EXCLUDED.source_event_count, "
            "    source_first_event_at = EXCLUDED.source_first_event_at, "
            "    source_last_event_at = EXCLUDED.source_last_event_at, "
            "    pipeline_run_id = EXCLUDED.pipeline_run_id, "
            "    computed_at = EXCLUDED.computed_at"
        )

        for item in items:
            conn.execute(
                snapshot_upsert_stmt,
                {
                    "snapshot_date": item["snapshot_date"],
                    "local_id": item["local_id"],
                    "ingredient_id": item["ingredient_id"],
                    "ingredient_sku": item["ingredient_sku"],
                    "ingredient_name": item["ingredient_name"],
                    "category": item["category"],
                    "unit_of_measure": item["unit_of_measure"],
                    "current_stock": item["current_stock"],
                    "minimum_stock": item["minimum_stock"],
                    "stock_level_ratio": item["stock_level_ratio"],
                    "stock_deficit": item["stock_deficit"],
                    "is_stockout": item["is_stockout"],
                    "is_below_minimum": item["is_below_minimum"],
                    "inbound_quantity": item["inbound_quantity"],
                    "outbound_quantity": item["outbound_quantity"],
                    "insufficient_stock_attempts_count": item["insufficient_stock_attempts_count"],
                    "source_event_count": item["source_event_count"],
                    "source_first_event_at": item["source_first_event_at"],
                    "source_last_event_at": item["source_last_event_at"],
                    "pipeline_run_id": pipeline_run_id,
                    "computed_at": now_utc,
                },
            )

        # 2. INSERT Lineage
        lineage_stmt = text(
            "INSERT INTO reporting.inventory_health_lineage ("
            "    pipeline_run_id, event_id, snapshot_date, local_id, ingredient_id, processed_at"
            ") VALUES ("
            "    :pipeline_run_id, :event_id, :snapshot_date, :local_id, :ingredient_id, :processed_at"
            ") ON CONFLICT (pipeline_run_id, event_id) DO NOTHING"
        )
        for item in items:
            for eid in item.get("event_ids", []):
                conn.execute(
                    lineage_stmt,
                    {
                        "pipeline_run_id": pipeline_run_id,
                        "event_id": eid,
                        "snapshot_date": item["snapshot_date"],
                        "local_id": item["local_id"],
                        "ingredient_id": item["ingredient_id"],
                        "processed_at": now_utc,
                    },
                )

        # 3. INSERT Quarantine
        quarantine_stmt = text(
            "INSERT INTO reporting.inventory_health_quarantine ("
            "    quarantine_id, event_id, pipeline_run_id, event_type, reason_code, reason_detail, raw_payload, quarantined_at"
            ") VALUES ("
            "    :quarantine_id, :event_id, :pipeline_run_id, :event_type, :reason_code, :reason_detail, :raw_payload, :quarantined_at"
            ") ON CONFLICT (quarantine_id) DO NOTHING"
        )
        for q in quarantine_records:
            conn.execute(
                quarantine_stmt,
                {
                    "quarantine_id": q["quarantine_id"],
                    "event_id": q["event_id"],
                    "pipeline_run_id": pipeline_run_id,
                    "event_type": q["event_type"],
                    "reason_code": q["reason_code"],
                    "reason_detail": q["reason_detail"],
                    "raw_payload": json.dumps(q["raw_payload"]),
                    "quarantined_at": q["quarantined_at"],
                },
            )

        # 4. UPDATE Checkpoint (only if watermark is available)
        if latest_event_ts and latest_event_id:
            checkpoint_stmt = text(
                "INSERT INTO reporting.pipeline_checkpoints ("
                "    pipeline_name, source_name, watermark_timestamp, watermark_event_id, last_successful_run_id, updated_at"
                ") VALUES ("
                "    'inventory_health_business', 'telemetry_events', :watermark_ts, :watermark_eid, :run_id, :updated_at"
                ") ON CONFLICT (pipeline_name, source_name) DO UPDATE SET "
                "    watermark_timestamp = EXCLUDED.watermark_timestamp, "
                "    watermark_event_id = EXCLUDED.watermark_event_id, "
                "    last_successful_run_id = EXCLUDED.last_successful_run_id, "
                "    updated_at = EXCLUDED.updated_at"
            )
            conn.execute(
                checkpoint_stmt,
                {
                    "watermark_ts": latest_event_ts,
                    "watermark_eid": latest_event_id,
                    "run_id": pipeline_run_id,
                    "updated_at": now_utc,
                },
            )

        # 5. UPDATE Execution Log to COMPLETED
        exec_log_stmt = text(
            "UPDATE reporting.pipeline_execution_logs SET "
            "    completed_at = :completed_at, "
            "    pipeline_run_status = 'COMPLETED', "
            "    watermark_timestamp = :watermark_ts, "
            "    source_events_read = :source_events_read, "
            "    records_quarantined = :records_quarantined "
            "WHERE pipeline_run_id = :run_id"
        )
        conn.execute(
            exec_log_stmt,
            {
                "completed_at": now_utc,
                "watermark_ts": latest_event_ts,
                "source_events_read": validated_data.get("total_read", 0),
                "records_quarantined": len(quarantine_records),
                "run_id": pipeline_run_id,
            },
        )

    return {
        "status": "COMPLETED",
        "snapshots_loaded": len(items),
        "quarantined_count": len(quarantine_records),
        "watermark_timestamp": latest_event_ts.isoformat() if latest_event_ts else None,
        "pipeline_run_id": pipeline_run_id,
    }


# ==============================================================================
# Task 6: Optional Non-Critical Task (publish_pipeline_summary)
# ==============================================================================
@task(name="publish_pipeline_summary")
def publish_pipeline_summary(
    load_result: dict[str, Any],
    should_fail: bool = False,
) -> dict[str, Any]:
    """
    Non-critical secondary task that formats a structured run summary.
    Invoked with return_state=True so its failure cannot mark a successful flow as FAILED.
    """
    if should_fail:
        raise ValueError("Simulated failure in non-critical publish_pipeline_summary task.")

    summary = {
        "pipeline_run_id": load_result.get("pipeline_run_id"),
        "status": load_result.get("status"),
        "snapshots_loaded": load_result.get("snapshots_loaded", 0),
        "quarantined_count": load_result.get("quarantined_count", 0),
        "published_at": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("Pipeline Summary Published: %s", summary)
    return summary


# ==============================================================================
# Subflow 1: Extract Inventory Health Data Flow
# ==============================================================================
@flow(
    name="extract-inventory-health-data",
    description="Subflow executing the data extraction phase from telemetry and transactional kardex.",
    log_prints=True,
)
def extract_inventory_health_data_flow(
    db_url: Optional[str] = None,
    is_full_reconciliation: bool = False,
) -> dict[str, Any]:
    """
    Subflow encapsulating data extraction.
    Invokes task 'extract_inventory_changes' and returns extracted datasets.
    """
    logger.info("Executing extract_inventory_health_data_flow...")
    return extract_inventory_changes(
        db_url=db_url,
        is_full_reconciliation=is_full_reconciliation,
    )


# ==============================================================================
# Subflow 2: Transform Inventory Health Data Flow
# ==============================================================================
@flow(
    name="transform-inventory-health-data",
    description="Subflow executing data validation, quarantine routing, ledger reconciliation, and KPI calculation.",
    log_prints=True,
)
def transform_inventory_health_data_flow(
    extracted_data: dict[str, Any],
) -> dict[str, Any]:
    """
    Subflow encapsulating in-memory data transformation:
    1. validate_and_deduplicate_events
    2. reconcile_inventory_ledger
    3. calculate_inventory_health_metrics
    Operates without global mutable state and is independently testable.
    """
    logger.info("Executing transform_inventory_health_data_flow...")
    validated = validate_and_deduplicate_events(extracted_data)
    reconciled = reconcile_inventory_ledger(extracted_data, validated)
    metrics = calculate_inventory_health_metrics(reconciled)

    return {
        "validated": validated,
        "reconciled": reconciled,
        "metrics": metrics,
    }


# ==============================================================================
# Subflow 3: Load Inventory Health Snapshot Flow
# ==============================================================================
@flow(
    name="load-inventory-health-snapshot",
    description="Subflow executing atomic idempotent loading into the reporting schema.",
    log_prints=True,
)
def load_inventory_health_snapshot_flow(
    metrics_data: dict[str, Any],
    validated_data: dict[str, Any],
    extracted_data: dict[str, Any],
    pipeline_run_id: str,
    db_url: Optional[str] = None,
) -> dict[str, Any]:
    """
    Subflow encapsulating the loading phase:
    Invokes task 'load_inventory_health_snapshot' inside an atomic transaction.
    """
    logger.info("Executing load_inventory_health_snapshot_flow for run %s...", pipeline_run_id)
    return load_inventory_health_snapshot(
        metrics_data=metrics_data,
        validated_data=validated_data,
        extracted_data=extracted_data,
        pipeline_run_id=pipeline_run_id,
        db_url=db_url,
    )


# ==============================================================================
# Flow: inventory_health_business_flow
# ==============================================================================
@flow(
    name="inventory-health-business",
    description="Business performance pipeline computing inventory health snapshots and KPIs.",
    log_prints=True,
)
def inventory_health_business_flow(
    db_url: Optional[str] = None,
    is_full_reconciliation: bool = False,
    run_id: Optional[str] = None,
    should_fail_summary: bool = False,
) -> dict[str, Any]:
    """
    Main Prefect 3 flow coordinating the 3 subflows + 1 optional secondary task:
    1. Subflow: extract_inventory_health_data_flow
    2. Subflow: transform_inventory_health_data_flow
    3. Subflow: load_inventory_health_snapshot_flow
    4. Task: publish_pipeline_summary (optional, return_state=True)
    """
    pipeline_run_id = str(UUID(run_id)) if run_id else str(uuid.uuid4())
    engine = _get_engine(db_url)
    is_postgres = engine.dialect.name == "postgresql"

    # 1. Concurrency control via PostgreSQL advisory lock
    lock_conn = engine.connect()
    has_lock = True
    if is_postgres:
        try:
            lock_res = lock_conn.execute(
                text(f"SELECT pg_try_advisory_lock({PIPELINE_ADVISORY_LOCK_ID})")
            ).scalar()
            has_lock = bool(lock_res)
        except Exception as e:
            logger.warning("Could not test advisory lock: %s", e)
            has_lock = True

    if not has_lock:
        lock_conn.close()
        logger.warning(
            "Another inventory_health_business_flow instance is actively running. Skipping run %s.",
            pipeline_run_id,
        )
        # Record SKIPPED state in execution logs
        record_execution_start(engine, UUID(pipeline_run_id), status="SKIPPED")
        return {
            "flow_run_id": pipeline_run_id,
            "status": "SKIPPED",
            "message": "Pipeline run skipped due to active concurrency lock.",
        }

    try:
        # Initialize RUNNING status in execution logs
        record_execution_start(engine, UUID(pipeline_run_id), status="RUNNING")

        # Subflow 1: Extraction
        extracted = extract_inventory_health_data_flow(
            db_url=db_url,
            is_full_reconciliation=is_full_reconciliation,
        )

        # Subflow 2: Transformation (Validation, Deduplication, Reconciliation & KPI Calculation)
        transformed = transform_inventory_health_data_flow(
            extracted_data=extracted,
        )
        validated = transformed["validated"]
        metrics = transformed["metrics"]

        # Subflow 3: Loading (Atomic Idempotent UPSERT, Checkpoint, Lineage, Quarantine & Exec Log)
        load_result = load_inventory_health_snapshot_flow(
            metrics_data=metrics,
            validated_data=validated,
            extracted_data=extracted,
            pipeline_run_id=pipeline_run_id,
            db_url=db_url,
        )

        # Stage 4: Optional Non-Critical Summary Task
        # Invoked explicitly with return_state=True to prevent secondary failure from aborting the flow
        summary_state = publish_pipeline_summary(
            load_result,
            should_fail=should_fail_summary,
            return_state=True,
        )
        if summary_state.is_failed():
            logger.warning("Secondary task publish_pipeline_summary failed, but main flow remains COMPLETED.")

        return {
            "flow_run_id": pipeline_run_id,
            "status": "COMPLETED",
            "snapshots_loaded": load_result["snapshots_loaded"],
            "records_quarantined": load_result["quarantined_count"],
            "events_read": validated.get("total_read", 0),
            "metrics": metrics.get("aggregated_metrics", {}),
        }

    except Exception as exc:
        logger.error("Pipeline run %s failed with exception: %s", pipeline_run_id, exc)
        sanitized_error = f"{exc.__class__.__name__}: {str(exc).splitlines()[0] if str(exc) else 'Pipeline failure'}"
        try:
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "UPDATE reporting.pipeline_execution_logs SET "
                        "    completed_at = :completed_at, "
                        "    pipeline_run_status = 'FAILED', "
                        "    error_detail = :error_detail "
                        "WHERE pipeline_run_id = :run_id"
                    ),
                    {
                        "completed_at": datetime.now(timezone.utc),
                        "error_detail": sanitized_error,
                        "run_id": pipeline_run_id,
                    },
                )
        except Exception as log_err:
            logger.error("Failed to update execution log to FAILED: %s", log_err)
        raise

    finally:
        if is_postgres and has_lock:
            try:
                lock_conn.execute(
                    text(f"SELECT pg_advisory_unlock({PIPELINE_ADVISORY_LOCK_ID})")
                )
            except Exception as e:
                logger.warning("Error releasing advisory lock: %s", e)
        lock_conn.close()


def trigger_inventory_health_flow(
    db_url: Optional[str] = None,
    triggered_by: Optional[str] = None,
) -> dict[str, Any]:
    """
    Asynchronously enqueues or triggers the inventory health flow.
    Persists initial state 'SCHEDULED' before returning.
    Returns HTTP 202 compatible response dictionary.
    """
    flow_run_id = str(uuid.uuid4())
    engine = _get_engine(db_url)
    now_utc = datetime.now(timezone.utc)

    # Persist initial SCHEDULED state
    record_execution_start(
        engine,
        UUID(flow_run_id),
        status="SCHEDULED",
        started_at=now_utc,
    )

    return {
        "flow_run_id": flow_run_id,
        "status": "SCHEDULED",
        "enqueued_at": now_utc.isoformat(),
        "triggered_by": str(triggered_by) if triggered_by else None,
        "message": "Inventory health business pipeline run enqueued successfully.",
    }
