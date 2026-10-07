"""
test_telemetry_report_api.py — Functional & Integration Tests for GET /telemetry/report and In-Memory Cache

Validates:
- Explicit dates and default 7-day period.
- UTC window resolution and validation (start_date < end_date).
- Invalid range returns HTTP 400 with clear message.
- Exact JSON response structure and typing.
- Empty table returns HTTP 200 with empty arrays.
- Database error handling returns HTTP 503 without leaking credentials.
- In-memory cache behavior:
  - Cache hit on repeated identical requests within 60s.
  - Cache miss on changed date window.
  - Re-execution after TTL expiration.
  - Consecutive parameterless requests share cached result without millisecond drift.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.domains.telemetry.cache import report_cache
from app.domains.telemetry.models import TelemetryEventRecord


@pytest.fixture(autouse=True)
def clean_cache():
    """Ensure clean cache before each test."""
    report_cache.clear()
    yield
    report_cache.clear()


def insert_sample_event(
    session: Session,
    event_type: str,
    ts: datetime,
    tags: dict | None = None,
):
    rec = TelemetryEventRecord(
        event_id=uuid.uuid4(),
        event_type=event_type,
        timestamp=ts,
        service="backoffice",
        session_id=str(uuid.uuid4()),
        user_id=uuid.uuid4(),
        request_id=f"req-{uuid.uuid4().hex[:8]}",
        tags=tags or {},
    )
    session.add(rec)
    session.commit()
    return rec


# --- 1. Endpoint tests ---

def test_report_endpoint_empty_db(client: TestClient):
    """Empty database returns 200 with all metric lists empty."""
    resp = client.get("/telemetry/report")
    assert resp.status_code == 200
    data = resp.json()

    assert "period" in data
    assert "from" in data["period"]
    assert "to" in data["period"]

    metrics = data["metrics"]
    assert metrics["events_per_day"] == []
    assert metrics["error_rate_by_type"] == []
    assert metrics["login_failure_rate_per_day"] == []
    assert metrics["api_latency_by_route"] == []


def test_report_endpoint_default_seven_day_window(client: TestClient):
    """When no dates are provided, defaults to 7-day window ending now."""
    resp = client.get("/telemetry/report")
    assert resp.status_code == 200
    data = resp.json()

    start_dt = datetime.fromisoformat(data["period"]["from"].replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(data["period"]["to"].replace("Z", "+00:00"))

    delta = end_dt - start_dt
    assert abs(delta.total_seconds() - 7 * 86400) < 5  # Exactly ~7 days


def test_report_endpoint_explicit_dates(client: TestClient, db_session: Session):
    """Explicit start_date and end_date ISO strings are respected."""
    now = datetime.now(timezone.utc)
    # Event within window
    insert_sample_event(db_session, "user_logged_in", now - timedelta(days=2))
    # Event outside window
    insert_sample_event(db_session, "user_logged_in", now - timedelta(days=10))

    start_iso = (now - timedelta(days=5)).isoformat()
    end_iso = now.isoformat()

    resp = client.get("/telemetry/report", params={"start_date": start_iso, "end_date": end_iso})
    assert resp.status_code == 200
    data = resp.json()

    assert len(data["metrics"]["events_per_day"]) == 1
    assert data["metrics"]["events_per_day"][0]["event_count"] == 1


def test_report_endpoint_invalid_range_rejected(client: TestClient):
    """Rejects start_date >= end_date with HTTP 400."""
    start = "2026-09-22T10:00:00Z"
    end = "2026-09-20T10:00:00Z"  # Earlier than start

    resp = client.get(f"/telemetry/report?start_date={start}&end_date={end}")
    assert resp.status_code == 400
    assert "start_date must be strictly earlier than end_date" in resp.json()["detail"]

    # Exactly equal
    resp_eq = client.get(f"/telemetry/report?start_date={start}&end_date={start}")
    assert resp_eq.status_code == 400


def test_report_endpoint_exact_json_structure(client: TestClient, db_session: Session):
    """Verifies complete contract structure and types."""
    now = datetime.now(timezone.utc)
    insert_sample_event(db_session, "user_logged_in", now - timedelta(days=1))
    insert_sample_event(db_session, "user_login_failed", now - timedelta(days=1))
    insert_sample_event(db_session, "form_validation_failed", now - timedelta(days=1))
    insert_sample_event(
        db_session,
        "api_latency_recorded",
        now - timedelta(days=1),
        tags={"route_path": "/inventory/products", "duration_ms": 125.0},
    )

    resp = client.get("/telemetry/report")
    assert resp.status_code == 200
    data = resp.json()

    assert set(data.keys()) == {"period", "metrics"}
    assert set(data["period"].keys()) == {"from", "to"}
    assert set(data["metrics"].keys()) == {
        "events_per_day",
        "error_rate_by_type",
        "login_failure_rate_per_day",
        "api_latency_by_route",
    }

    # Verify item shapes
    epd = data["metrics"]["events_per_day"][0]
    assert "date" in epd and "event_count" in epd

    ert = data["metrics"]["error_rate_by_type"][0]
    assert "event_type" in ert and "error_count" in ert and "error_rate" in ert

    lfr = data["metrics"]["login_failure_rate_per_day"][0]
    assert all(k in lfr for k in ("date", "successful_logins", "failed_logins", "total_attempts", "login_failure_rate"))

    lat = data["metrics"]["api_latency_by_route"][0]
    assert all(k in lat for k in ("route_path", "request_count", "average_duration_ms", "p95_duration_ms"))


def test_report_endpoint_database_error_handling(client: TestClient):
    """Database failure raises HTTP 503 without leaking internal connection info."""
    with patch(
        "app.domains.telemetry.service.get_events_per_day",
        side_effect=Exception("FATAL: password authentication failed for user postgres"),
    ):
        resp = client.get("/telemetry/report")
        assert resp.status_code == 503
        # Must not leak the password or error details
        assert resp.json()["detail"] == "Database service temporarily unavailable"
        assert "password" not in resp.text
        assert "FATAL" not in resp.text


# --- 2. In-Memory Cache Tests ---

def test_cache_hit_avoids_repeated_queries(client: TestClient, db_session: Session):
    """Two identical requests within 60s execute analysis metrics only once."""
    now = datetime.now(timezone.utc)
    insert_sample_event(db_session, "user_logged_in", now - timedelta(days=1))

    start = "2026-09-15T00:00:00Z"
    end = "2026-09-22T00:00:00Z"
    url = f"/telemetry/report?start_date={start}&end_date={end}"

    with patch("app.domains.telemetry.service.get_events_per_day", wraps=lambda s, st, et: [{"date": "2026-09-20", "event_count": 1}]) as spy_metric:
        resp1 = client.get(url)
        assert resp1.status_code == 200
        assert spy_metric.call_count == 1

        resp2 = client.get(url)
        assert resp2.status_code == 200
        # Call count must still be 1 (cache hit avoided query)
        assert spy_metric.call_count == 1
        assert resp1.json() == resp2.json()


def test_cache_miss_on_date_change(client: TestClient):
    """Changing date range produces a cache miss and executes fresh query."""
    start1 = "2026-09-15T00:00:00Z"
    start2 = "2026-09-16T00:00:00Z"
    end = "2026-09-22T00:00:00Z"

    with patch("app.domains.telemetry.service.get_events_per_day", return_value=[]) as spy_metric:
        client.get(f"/telemetry/report?start_date={start1}&end_date={end}")
        assert spy_metric.call_count == 1

        client.get(f"/telemetry/report?start_date={start2}&end_date={end}")
        assert spy_metric.call_count == 2


def test_cache_expiration_after_ttl(client: TestClient):
    """Expired entry after TTL (60s) causes re-execution."""
    start = "2026-09-15T00:00:00Z"
    end = "2026-09-22T00:00:00Z"
    url = f"/telemetry/report?start_date={start}&end_date={end}"

    with patch("app.domains.telemetry.service.get_events_per_day", return_value=[]) as spy_metric:
        client.get(url)
        assert spy_metric.call_count == 1

        # Simulate monotonic clock moving 61 seconds into future
        real_monotonic = time.monotonic()
        with patch("time.monotonic", return_value=real_monotonic + 61.0):
            client.get(url)
            assert spy_metric.call_count == 2


def test_cache_parameterless_calls_share_resolved_window(client: TestClient):
    """
    Two calls without parameters within TTL reuse the exact same resolved window,
    avoiding cache misses from microsecond differences in datetime.now().
    """
    resp1 = client.get("/telemetry/report")
    assert resp1.status_code == 200
    p1 = resp1.json()["period"]

    time.sleep(0.05)

    resp2 = client.get("/telemetry/report")
    assert resp2.status_code == 200
    p2 = resp2.json()["period"]

    assert p1["from"] == p2["from"]
    assert p1["to"] == p2["to"]
    assert resp1.json() == resp2.json()
