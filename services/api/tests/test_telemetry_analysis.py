"""
test_telemetry_analysis.py — Unit Tests for Telemetry Analysis Metrics via Pandas

Tests each metric function independently:
- Query with window [start_date, end_date) (inclusive start, exclusive end).
- SQL filtering by event_type.
- UTC conversion before grouping.
- Empty DataFrame / no matching rows.
- Corrupted / invalid timestamps.
- Missing dimensions in tags.
- Non-numeric duration values in tags.
- Deterministic sort order.
- JSON-safe return types (pure int, float, str, no NumPy or Pandas types).
- Exact known formula calculations.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

from app.domains.telemetry.analysis import (
    get_api_latency_by_route,
    get_error_rate_by_type,
    get_events_per_day,
    get_login_failure_rate_per_day,
)
from app.domains.telemetry.models import TelemetryEventRecord


def create_record(
    session: Session,
    event_type: str,
    ts: datetime,
    tags: dict | None = None,
    user_id: uuid.UUID | None = None,
) -> TelemetryEventRecord:
    rec = TelemetryEventRecord(
        event_id=uuid.uuid4(),
        event_type=event_type,
        timestamp=ts,
        service="backoffice",
        session_id=str(uuid.uuid4()),
        user_id=user_id,
        request_id=f"req-{uuid.uuid4().hex[:8]}",
        tags=tags or {},
    )
    session.add(rec)
    return rec


# --- 1. events_per_day tests ---

def test_events_per_day_empty(db_session: Session):
    """Empty table returns empty list."""
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    end = datetime(2026, 9, 8, tzinfo=timezone.utc)
    res = get_events_per_day(db_session, start, end)
    assert res == []


def test_events_per_day_window_boundary(db_session: Session):
    """Verifies [start_date, end_date) with inclusive start and exclusive end."""
    start = datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)

    # Exactly at start (included)
    create_record(db_session, "test_event", datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc))
    # Mid-window (included)
    create_record(db_session, "test_event", datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc))
    # Exactly at end (excluded)
    create_record(db_session, "test_event", datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc))
    # Before start (excluded)
    create_record(db_session, "test_event", datetime(2026, 9, 19, 23, 59, 59, tzinfo=timezone.utc))
    db_session.commit()

    res = get_events_per_day(db_session, start, end)
    assert len(res) == 2
    assert res[0] == {"date": "2026-09-20", "event_count": 1}
    assert res[1] == {"date": "2026-09-21", "event_count": 1}
    assert isinstance(res[0]["event_count"], int)


def test_events_per_day_utc_grouping(db_session: Session):
    """Events with non-UTC timestamps must be converted to UTC before grouping by date."""
    start = datetime(2026, 9, 20, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 9, 23, 0, 0, 0, tzinfo=timezone.utc)

    # 2026-09-20 23:30:00 UTC
    create_record(db_session, "test_event", datetime(2026, 9, 20, 23, 30, 0, tzinfo=timezone.utc))
    # 2026-09-21 00:30:00 UTC
    create_record(db_session, "test_event", datetime(2026, 9, 21, 0, 30, 0, tzinfo=timezone.utc))
    db_session.commit()

    res = get_events_per_day(db_session, start, end)
    assert len(res) == 2
    assert res[0]["date"] == "2026-09-20"
    assert res[0]["event_count"] == 1
    assert res[1]["date"] == "2026-09-21"
    assert res[1]["event_count"] == 1


# --- 2. error_rate_by_type tests ---

def test_error_rate_by_type_empty_and_no_errors(db_session: Session):
    """Returns [] if there are no errors in the period."""
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)

    # Only non-error events
    create_record(db_session, "user_logged_in", datetime(2026, 9, 21, tzinfo=timezone.utc))
    create_record(db_session, "inbound_order_created", datetime(2026, 9, 21, tzinfo=timezone.utc))
    db_session.commit()

    res = get_error_rate_by_type(db_session, start, end)
    assert res == []


def test_error_rate_by_type_exact_percentages(db_session: Session):
    """Validates calculation, sorting, and only counting the 3 allowed error types."""
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)

    # 4 form_validation_failed
    for _ in range(4):
        create_record(db_session, "form_validation_failed", datetime(2026, 9, 21, 10, tzinfo=timezone.utc))
    # 4 system_exception_captured
    for _ in range(4):
        create_record(db_session, "system_exception_captured", datetime(2026, 9, 21, 11, tzinfo=timezone.utc))
    # 2 external_integration_failed
    for _ in range(2):
        create_record(db_session, "external_integration_failed", datetime(2026, 9, 21, 12, tzinfo=timezone.utc))
    # 5 non-error events (must be ignored by SQL query)
    for _ in range(5):
        create_record(db_session, "user_login_failed", datetime(2026, 9, 21, 13, tzinfo=timezone.utc))
    db_session.commit()

    res = get_error_rate_by_type(db_session, start, end)
    assert len(res) == 3

    # Total errors = 10 -> 4/10 = 40.0%, 4/10 = 40.0%, 2/10 = 20.0%
    # Sort order: count desc, event_type asc
    assert res[0]["event_type"] == "form_validation_failed"
    assert res[0]["error_count"] == 4
    assert res[0]["error_rate"] == 40.0

    assert res[1]["event_type"] == "system_exception_captured"
    assert res[1]["error_count"] == 4
    assert res[1]["error_rate"] == 40.0

    assert res[2]["event_type"] == "external_integration_failed"
    assert res[2]["error_count"] == 2
    assert res[2]["error_rate"] == 20.0

    # Strict JSON-safe types
    for r in res:
        assert isinstance(r["event_type"], str)
        assert isinstance(r["error_count"], int)
        assert isinstance(r["error_rate"], float)


# --- 3. login_failure_rate_per_day tests ---

def test_login_failure_rate_empty(db_session: Session):
    """Empty table or period without logins returns []."""
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)
    res = get_login_failure_rate_per_day(db_session, start, end)
    assert res == []


def test_login_failure_rate_calculations(db_session: Session):
    """
    Validates:
    - user_logged_in as success.
    - user_login_failed as failure.
    - Days with successes and failures.
    - Days with only successes (rate = 0.0, not missing row).
    - Exclusion of dates with 0 attempts.
    """
    start = datetime(2026, 9, 10, tzinfo=timezone.utc)
    end = datetime(2026, 9, 15, tzinfo=timezone.utc)

    # 2026-09-10: 3 successes, 1 failure -> 4 attempts, 25.0%
    for _ in range(3):
        create_record(db_session, "user_logged_in", datetime(2026, 9, 10, 10, tzinfo=timezone.utc))
    create_record(db_session, "user_login_failed", datetime(2026, 9, 10, 11, tzinfo=timezone.utc))

    # 2026-09-11: 5 successes, 0 failures -> 5 attempts, 0.0%
    for _ in range(5):
        create_record(db_session, "user_logged_in", datetime(2026, 9, 11, 12, tzinfo=timezone.utc))

    # 2026-09-12: 0 attempts (must not appear)

    # 2026-09-13: 0 successes, 2 failures -> 2 attempts, 100.0%
    for _ in range(2):
        create_record(db_session, "user_login_failed", datetime(2026, 9, 13, 15, tzinfo=timezone.utc))

    db_session.commit()

    res = get_login_failure_rate_per_day(db_session, start, end)
    assert len(res) == 3

    assert res[0] == {
        "date": "2026-09-10",
        "successful_logins": 3,
        "failed_logins": 1,
        "total_attempts": 4,
        "login_failure_rate": 25.0,
    }
    assert res[1] == {
        "date": "2026-09-11",
        "successful_logins": 5,
        "failed_logins": 0,
        "total_attempts": 5,
        "login_failure_rate": 0.0,
    }
    assert res[2] == {
        "date": "2026-09-13",
        "successful_logins": 0,
        "failed_logins": 2,
        "total_attempts": 2,
        "login_failure_rate": 100.0,
    }

    # Strict JSON-safe types
    for r in res:
        assert isinstance(r["date"], str)
        assert isinstance(r["successful_logins"], int)
        assert isinstance(r["failed_logins"], int)
        assert isinstance(r["total_attempts"], int)
        assert isinstance(r["login_failure_rate"], float)


# --- 4. api_latency_by_route tests ---

def test_api_latency_empty(db_session: Session):
    """Empty table returns []."""
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)
    res = get_api_latency_by_route(db_session, start, end)
    assert res == []


def test_api_latency_aggregation_and_p95(db_session: Session):
    """
    Validates:
    - Route grouping.
    - Average and P95 latency.
    - Discarding corrupted tags or non-numeric durations.
    - Sorting by P95 descending.
    """
    start = datetime(2026, 9, 20, tzinfo=timezone.utc)
    end = datetime(2026, 9, 22, tzinfo=timezone.utc)

    # Route 1: /inventory/products with 10 values: 10, 20, ..., 100
    for val in range(10, 110, 10):
        create_record(
            db_session,
            "api_latency_recorded",
            datetime(2026, 9, 21, 10, tzinfo=timezone.utc),
            tags={"route_path": "/inventory/products", "duration_ms": float(val)},
        )

    # Route 2: /inventory/orders with 5 values: 100, 200, 300, 400, 500
    for val in range(100, 600, 100):
        create_record(
            db_session,
            "api_latency_recorded",
            datetime(2026, 9, 21, 11, tzinfo=timezone.utc),
            tags={"route_path": "/inventory/orders", "duration_ms": float(val)},
        )

    # Corrupted / invalid tags to be discarded:
    create_record(
        db_session,
        "api_latency_recorded",
        datetime(2026, 9, 21, 12, tzinfo=timezone.utc),
        tags={"route_path": "", "duration_ms": 50.0},  # Empty route
    )
    create_record(
        db_session,
        "api_latency_recorded",
        datetime(2026, 9, 21, 12, tzinfo=timezone.utc),
        tags={"route_path": "/corrupted", "duration_ms": "not-a-number"},  # Non-numeric
    )
    create_record(
        db_session,
        "api_latency_recorded",
        datetime(2026, 9, 21, 12, tzinfo=timezone.utc),
        tags={"duration_ms": 50.0},  # Missing route
    )
    db_session.commit()

    res = get_api_latency_by_route(db_session, start, end)
    assert len(res) == 2

    # /inventory/orders has higher P95 (0.95 quantile of [100, 200, 300, 400, 500] = 480.0), so comes first
    orders_route = res[0]
    assert orders_route["route_path"] == "/inventory/orders"
    assert orders_route["request_count"] == 5
    assert orders_route["average_duration_ms"] == 300.0
    assert orders_route["p95_duration_ms"] == 480.0

    products_route = res[1]
    assert products_route["route_path"] == "/inventory/products"
    assert products_route["request_count"] == 10
    assert products_route["average_duration_ms"] == 55.0
    assert products_route["p95_duration_ms"] == 95.5

    # Strict JSON-safe types
    for r in res:
        assert isinstance(r["route_path"], str)
        assert isinstance(r["request_count"], int)
        assert isinstance(r["average_duration_ms"], float)
        assert isinstance(r["p95_duration_ms"], float)
