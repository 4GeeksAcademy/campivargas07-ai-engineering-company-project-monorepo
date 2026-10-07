"""
test_reporting_api.py — API Integration & Security Tests for Reporting Domain

Validates:
1. Authentication: 401 Unauthorized when Bearer token is missing.
2. Authorization: 403 Forbidden for 'user' and 'employee' roles on POST /reporting/inventory-health/runs.
3. 202 Accepted for 'admin' and 'manager' roles on POST /reporting/inventory-health/runs.
4. GET /reporting/inventory-health/runs/{flow_run_id}: 404 on missing, 200 on existing, sanitized errors.
5. GET /reporting/inventory-health: 200 with period, summary, items, and filters (local_id, ingredient_id, only_critical).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.database import get_db
from app.domains.auth.service import create_access_token
from app.main import app

pytestmark = pytest.mark.postgres
TEST_DB_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture(scope="module")
def pg_api_engine():
    """Provides a PostgreSQL engine initialized with both telemetry and reporting migrations."""
    if not TEST_DB_URL:
        pytest.skip("TEST_DATABASE_URL not configured. Skipping PostgreSQL API tests.")

    engine = create_engine(TEST_DB_URL, pool_pre_ping=True)

    mig1_path = Path(__file__).resolve().parent.parent / "migrations" / "001_create_telemetry_events.sql"
    with engine.connect() as conn:
        conn.execute(text(mig1_path.read_text(encoding="utf-8")))
        conn.commit()

    mig2_path = Path(__file__).resolve().parent.parent / "migrations" / "002_create_inventory_health_reporting.sql"
    with engine.connect() as conn:
        conn.execute(text(mig2_path.read_text(encoding="utf-8")))
        conn.commit()

    from app.database import init_db
    init_db(bind_engine=engine)

    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_reporting_api_tables(pg_api_engine):
    """Truncates reporting tables before each test to ensure test isolation."""
    with pg_api_engine.begin() as conn:
        conn.execute(text("TRUNCATE reporting.inventory_health_snapshot CASCADE;"))
        conn.execute(text("TRUNCATE reporting.pipeline_execution_logs CASCADE;"))


@pytest.fixture
def auth_headers_by_role(create_test_user):
    """Factory fixture generating headers for specific user roles."""
    def _headers(role: str) -> dict[str, str]:
        user = create_test_user(email=f"{role}_{uuid.uuid4().hex[:6]}@brasaland.com", role=role)
        token = create_access_token(data={"sub": str(user.doc_id), "role": user["role"]})
        return {"Authorization": f"Bearer {token}"}
    return _headers


@pytest.fixture
def api_client(pg_api_engine):
    """TestClient bound to TEST_DATABASE_URL."""
    with TestClient(app) as test_client:
        yield test_client


def test_reporting_endpoints_require_authentication(api_client):
    """All reporting endpoints must return 401 Unauthorized without Bearer token."""
    res1 = api_client.post("/reporting/inventory-health/runs")
    assert res1.status_code == 401

    res2 = api_client.get("/reporting/inventory-health/runs/latest")
    assert res2.status_code == 401

    res3 = api_client.get("/reporting/inventory-health")
    assert res3.status_code == 401


def test_trigger_run_role_authorization(api_client, auth_headers_by_role):
    """
    POST /reporting/inventory-health/runs:
    - role 'user' -> 403 Forbidden
    - role 'employee' -> 403 Forbidden
    - role 'manager' -> 202 Accepted
    - role 'admin' -> 202 Accepted
    """
    from unittest.mock import patch

    with patch("app.domains.reporting.service._run_pipeline_background"):
        user_headers = auth_headers_by_role("user")
        res_user = api_client.post("/reporting/inventory-health/runs", headers=user_headers)
        assert res_user.status_code == 403
        assert "Forbidden" in res_user.json()["detail"]

        emp_headers = auth_headers_by_role("employee")
        res_emp = api_client.post("/reporting/inventory-health/runs", headers=emp_headers)
        assert res_emp.status_code == 403

        mgr_headers = auth_headers_by_role("manager")
        res_mgr = api_client.post("/reporting/inventory-health/runs", headers=mgr_headers)
        assert res_mgr.status_code == 202
        body_mgr = res_mgr.json()
        assert body_mgr["status"] == "SCHEDULED"
        assert "flow_run_id" in body_mgr
        assert "enqueued_at" in body_mgr

        admin_headers = auth_headers_by_role("admin")
        res_admin = api_client.post("/reporting/inventory-health/runs", headers=admin_headers)
        assert res_admin.status_code == 202
        body_admin = res_admin.json()
        assert body_admin["status"] == "SCHEDULED"


def test_get_run_status_not_found(api_client, auth_headers_by_role):
    """GET /reporting/inventory-health/runs/{id} returns 404 for unknown run."""
    headers = auth_headers_by_role("manager")
    random_uuid = str(uuid.uuid4())
    res = api_client.get(f"/reporting/inventory-health/runs/{random_uuid}", headers=headers)
    assert res.status_code == 404
    assert f"Pipeline run '{random_uuid}' not found." in res.json()["detail"]

    res_invalid = api_client.get("/reporting/inventory-health/runs/invalid-uuid", headers=headers)
    assert res_invalid.status_code == 404


def test_get_run_status_success_and_sanitized_error(api_client, auth_headers_by_role, pg_api_engine):
    """GET /reporting/inventory-health/runs/{id} returns 200 with counters and sanitized error."""
    headers = auth_headers_by_role("manager")
    run_id = uuid.uuid4()
    now_utc = datetime.now(timezone.utc)

    with pg_api_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO reporting.pipeline_execution_logs ("
                "    pipeline_run_id, started_at, completed_at, pipeline_run_status, source_events_read, records_quarantined, error_detail"
                ") VALUES ("
                "    :run_id, :started_at, :completed_at, 'FAILED', 150, 2, 'OperationalError: connection lost'"
                ")"
            ),
            {"run_id": run_id, "started_at": now_utc, "completed_at": now_utc},
        )

    res = api_client.get(f"/reporting/inventory-health/runs/{run_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["flow_run_id"] == str(run_id)
    assert data["status"] == "FAILED"
    assert data["counters"]["source_events_read"] == 150
    assert data["counters"]["records_quarantined"] == 2
    assert data["error_message"] == "OperationalError: connection lost"

    # Also test 'latest' alias
    res_latest = api_client.get("/reporting/inventory-health/runs/latest", headers=headers)
    assert res_latest.status_code == 200
    assert res_latest.json()["flow_run_id"] == str(run_id)


def test_get_inventory_health_kpis_and_filters(api_client, auth_headers_by_role, pg_api_engine):
    """
    GET /reporting/inventory-health:
    - Returns aggregated summary and items.
    - Validates local_id and only_critical filters.
    """
    headers = auth_headers_by_role("user")  # Regular user can read business KPIs
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")

    ing1_id = uuid.uuid4()
    ing2_id = uuid.uuid4()
    run_id = uuid.uuid4()

    with pg_api_engine.begin() as conn:
        # Item 1: MED-001, stockout
        conn.execute(
            text(
                "INSERT INTO reporting.inventory_health_snapshot ("
                "    snapshot_date, local_id, ingredient_id, ingredient_sku, ingredient_name, "
                "    category, unit_of_measure, current_stock, minimum_stock, stock_level_ratio, "
                "    stock_deficit, is_stockout, is_below_minimum, inbound_quantity, outbound_quantity, "
                "    insufficient_stock_attempts_count, source_event_count, pipeline_run_id, computed_at"
                ") VALUES ("
                "    :s_date, 'MED-001', :ing1_id, 'ING-API-01', 'Carne Res', "
                "    'carne', 'kg', 0.0, 25.0, 0.0, "
                "    25.0, true, true, 0.0, 0.0, "
                "    3, 5, :run_id, :computed_at"
                ")"
            ),
            {"s_date": today_str, "ing1_id": ing1_id, "run_id": run_id, "computed_at": now_utc},
        )
        # Item 2: MIA-001, healthy stock
        conn.execute(
            text(
                "INSERT INTO reporting.inventory_health_snapshot ("
                "    snapshot_date, local_id, ingredient_id, ingredient_sku, ingredient_name, "
                "    category, unit_of_measure, current_stock, minimum_stock, stock_level_ratio, "
                "    stock_deficit, is_stockout, is_below_minimum, inbound_quantity, outbound_quantity, "
                "    insufficient_stock_attempts_count, source_event_count, pipeline_run_id, computed_at"
                ") VALUES ("
                "    :s_date, 'MIA-001', :ing2_id, 'ING-API-02', 'Papas Fritas', "
                "    'acompañamiento', 'kg', 50.0, 20.0, 2.5, "
                "    0.0, false, false, 50.0, 0.0, "
                "    0, 2, :run_id, :computed_at"
                ")"
            ),
            {"s_date": today_str, "ing2_id": ing2_id, "run_id": run_id, "computed_at": now_utc},
        )

    # 1. Unfiltered query
    res = api_client.get(f"/reporting/inventory-health?date={today_str}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["period"]["snapshot_date"] == today_str
    assert data["summary"]["total_locations_reported"] == 2
    assert data["summary"]["total_ingredients_monitored"] == 2
    assert data["summary"]["critical_stockouts_count"] == 1
    assert data["summary"]["insufficient_stock_attempts_count"] == 3
    assert len(data["items"]) == 2

    # 2. Filter by local_id
    res_loc = api_client.get(f"/reporting/inventory-health?date={today_str}&local_id=MED-001", headers=headers)
    assert res_loc.status_code == 200
    data_loc = res_loc.json()
    assert len(data_loc["items"]) == 1
    assert data_loc["items"][0]["local_id"] == "MED-001"

    # 3. Filter by only_critical=true
    res_crit = api_client.get(f"/reporting/inventory-health?date={today_str}&only_critical=true", headers=headers)
    assert res_crit.status_code == 200
    data_crit = res_crit.json()
    assert len(data_crit["items"]) == 1
    assert data_crit["items"][0]["is_stockout"] is True
