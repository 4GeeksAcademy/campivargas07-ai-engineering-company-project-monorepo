"""
queries.py — Brasaland · Inventory Health Business Pipeline Reporting Queries

Provides authoritative query operations on the `reporting` schema:
- fetch_inventory_health_snapshot: Consolidated business KPIs and item detail.
- get_pipeline_run_status: Execution run status, counters, and sanitized errors.
- record_execution_start: Idempotent initialization of run log in reporting.pipeline_execution_logs.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _get_engine(engine_or_session_or_url: Any = None) -> Engine:
    """Helper to obtain an active SQLAlchemy Engine."""
    if isinstance(engine_or_session_or_url, Engine):
        return engine_or_session_or_url
    if hasattr(engine_or_session_or_url, "bind") and engine_or_session_or_url.bind is not None:
        return engine_or_session_or_url.bind
    if isinstance(engine_or_session_or_url, str):
        return create_engine(engine_or_session_or_url, pool_pre_ping=True)

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL or TEST_DATABASE_URL must be configured.")
    return create_engine(db_url, pool_pre_ping=True)


def get_pipeline_run_status(
    engine_or_url: Any = None,
    flow_run_id: str = "latest",
) -> Optional[dict[str, Any]]:
    """
    Fetches execution run status by UUID or 'latest'.
    Returns None if no matching execution is found.
    """
    engine = _get_engine(engine_or_url)
    with engine.connect() as conn:
        if flow_run_id == "latest":
            stmt = text(
                "SELECT pipeline_run_id, started_at, completed_at, pipeline_run_status, "
                "watermark_timestamp, source_events_read, records_quarantined, error_detail "
                "FROM reporting.pipeline_execution_logs "
                "ORDER BY started_at DESC LIMIT 1"
            )
            row = conn.execute(stmt).fetchone()
        else:
            try:
                run_uuid = UUID(flow_run_id)
            except ValueError:
                return None

            stmt = text(
                "SELECT pipeline_run_id, started_at, completed_at, pipeline_run_status, "
                "watermark_timestamp, source_events_read, records_quarantined, error_detail "
                "FROM reporting.pipeline_execution_logs "
                "WHERE pipeline_run_id = :run_id"
            )
            row = conn.execute(stmt, {"run_id": run_uuid}).fetchone()

        if row is None:
            return None

        (
            p_run_id,
            started_at,
            completed_at,
            status,
            _watermark,
            events_read,
            quarantined,
            error_detail,
        ) = row

        duration = None
        if started_at and completed_at:
            duration = round((completed_at - started_at).total_seconds(), 2)

        return {
            "flow_run_id": str(p_run_id),
            "status": status,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "duration_seconds": duration,
            "counters": {
                "source_events_read": events_read or 0,
                "records_quarantined": quarantined or 0,
            },
            "error_message": error_detail,
        }


def record_execution_start(
    engine_or_url: Any,
    pipeline_run_id: UUID,
    status: str = "RUNNING",
    started_at: Optional[datetime] = None,
) -> None:
    """Idempotently records the start of a pipeline run in reporting.pipeline_execution_logs."""
    engine = _get_engine(engine_or_url)
    start_ts = started_at or datetime.now(timezone.utc)
    stmt = text(
        "INSERT INTO reporting.pipeline_execution_logs ("
        "pipeline_run_id, started_at, pipeline_run_status, source_events_read, records_quarantined"
        ") VALUES ("
        ":run_id, :started_at, :status, 0, 0"
        ") ON CONFLICT (pipeline_run_id) DO NOTHING"
    )
    with engine.begin() as conn:
        conn.execute(
            stmt,
            {
                "run_id": pipeline_run_id,
                "started_at": start_ts,
                "status": status,
            },
        )


def fetch_inventory_health_snapshot(
    engine_or_url: Any = None,
    date: Optional[str] = None,
    local_id: Optional[str] = None,
    ingredient_id: Optional[UUID | str] = None,
    only_critical: bool = False,
) -> dict[str, Any]:
    """
    Queries reporting.inventory_health_snapshot and produces consolidated KPIs and items list.
    Does NOT query or depend on GET /telemetry/report.
    """
    engine = _get_engine(engine_or_url)

    with engine.connect() as conn:
        # 1. Resolve date
        if not date:
            max_date_row = conn.execute(
                text("SELECT MAX(snapshot_date) FROM reporting.inventory_health_snapshot")
            ).scalar()
            resolved_date = max_date_row.isoformat() if max_date_row else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        else:
            resolved_date = date

        # 2. Build parameterized query
        conditions = ["snapshot_date = :snapshot_date"]
        params: dict[str, Any] = {"snapshot_date": resolved_date}

        if local_id:
            conditions.append("local_id = :local_id")
            params["local_id"] = local_id

        if ingredient_id:
            conditions.append("ingredient_id = :ingredient_id")
            params["ingredient_id"] = str(ingredient_id)

        if only_critical:
            conditions.append("(is_stockout = TRUE OR is_below_minimum = TRUE)")

        where_clause = " AND ".join(conditions)
        query = text(
            f"SELECT snapshot_date, local_id, ingredient_id, ingredient_sku, ingredient_name, "
            f"category, unit_of_measure, current_stock, minimum_stock, stock_level_ratio, "
            f"stock_deficit, is_stockout, is_below_minimum, inbound_quantity, outbound_quantity, "
            f"insufficient_stock_attempts_count, source_event_count, source_first_event_at, "
            f"source_last_event_at, pipeline_run_id, computed_at "
            f"FROM reporting.inventory_health_snapshot "
            f"WHERE {where_clause} "
            f"ORDER BY is_stockout DESC, is_below_minimum DESC, stock_level_ratio ASC NULLS LAST, local_id ASC, ingredient_name ASC"
        )

        rows = conn.execute(query, params).fetchall()

        if not rows:
            now_utc = datetime.now(timezone.utc)
            return {
                "period": {
                    "snapshot_date": resolved_date,
                    "data_freshness_timestamp": None,
                    "freshness_lag_seconds": None,
                },
                "summary": {
                    "total_locations_reported": 0,
                    "total_ingredients_monitored": 0,
                    "critical_stockouts_count": 0,
                    "below_minimum_count": 0,
                    "average_stock_level_ratio": 0.0,
                    "insufficient_stock_attempts_count": 0,
                },
                "items": [],
                "pipeline_run_id": None,
            }

        # 3. Assemble items and summary
        items = []
        locations = set()
        ingredients = set()
        critical_stockouts = 0
        below_minimum = 0
        ratios = []
        total_insufficient_attempts = 0
        max_computed_at = None
        latest_pipeline_run_id = None

        for row in rows:
            (
                s_date,
                loc_id,
                ing_id,
                sku,
                name,
                cat,
                uom,
                cur_stock,
                min_stock,
                ratio,
                deficit,
                stockout,
                below_min,
                in_qty,
                out_qty,
                attempts,
                src_count,
                _first_evt,
                _last_evt,
                p_run_id,
                comp_at,
            ) = row

            locations.add(loc_id)
            ingredients.add(str(ing_id))
            if stockout:
                critical_stockouts += 1
            if below_min:
                below_minimum += 1
            if ratio is not None:
                ratios.append(float(ratio))
            total_insufficient_attempts += int(attempts or 0)

            if max_computed_at is None or (comp_at and comp_at > max_computed_at):
                max_computed_at = comp_at
            latest_pipeline_run_id = str(p_run_id)

            items.append(
                {
                    "local_id": str(loc_id),
                    "ingredient_id": str(ing_id),
                    "ingredient_sku": str(sku),
                    "ingredient_name": str(name),
                    "category": str(cat),
                    "unit_of_measure": str(uom),
                    "current_stock": float(cur_stock),
                    "minimum_stock": float(min_stock),
                    "stock_level_ratio": float(ratio) if ratio is not None else None,
                    "stock_deficit": float(deficit),
                    "is_stockout": bool(stockout),
                    "is_below_minimum": bool(below_min),
                    "inbound_quantity": float(in_qty or 0.0),
                    "outbound_quantity": float(out_qty or 0.0),
                    "insufficient_stock_attempts_count": int(attempts or 0),
                    "source_event_count": int(src_count or 0),
                    "computed_at": comp_at.isoformat() if comp_at else None,
                }
            )

        avg_ratio = round(sum(ratios) / len(ratios), 4) if ratios else 0.0

        now_utc = datetime.now(timezone.utc)
        freshness_lag = None
        if max_computed_at:
            if max_computed_at.tzinfo is None:
                max_computed_at = max_computed_at.replace(tzinfo=timezone.utc)
            freshness_lag = max(0, int((now_utc - max_computed_at).total_seconds()))

        return {
            "period": {
                "snapshot_date": resolved_date,
                "data_freshness_timestamp": max_computed_at.isoformat() if max_computed_at else None,
                "freshness_lag_seconds": freshness_lag,
            },
            "summary": {
                "total_locations_reported": len(locations),
                "total_ingredients_monitored": len(ingredients),
                "critical_stockouts_count": critical_stockouts,
                "below_minimum_count": below_minimum,
                "average_stock_level_ratio": avg_ratio,
                "insufficient_stock_attempts_count": total_insufficient_attempts,
            },
            "items": items,
            "pipeline_run_id": latest_pipeline_run_id,
        }
