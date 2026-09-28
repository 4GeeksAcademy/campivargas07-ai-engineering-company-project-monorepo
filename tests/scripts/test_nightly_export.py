"""
test_nightly_export.py — Brasaland · Unit and Integration Tests for Nightly Export (#DEV-53)

Tests:
1. Date resolution (CLI, env var, default yesterday UTC, invalid validation).
2. Export CSV filtering strictly by target date UTC range (no bleed into adjacent days).
3. Preserving pre-existing CSV without overwrite (idempotent backup).
4. Atomic claiming: skipping already completed target date.
5. Atomic claiming: retrying after previous failure.
6. Atomic claiming: recovering stale/zombie processing run after timeout.
7. Atomic claiming: preventing concurrent parallel executions.
8. CLI execution: full success cycle (pending -> processing -> completed).
9. CLI execution: handling pipeline SKIPPED (marks failed, does NOT mark completed).
10. CLI execution: handling pipeline failure (marks failed with error detail).
11. CLI execution: idempotent skip when already completed.
"""

from __future__ import annotations

import csv
import json
import subprocess
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, select

from app.database import init_db
from app.domains.jobs.models import JobRunRecord
from app.domains.jobs.service import (
    claim_job_run,
    complete_job_run,
    fail_job_run,
)
from app.domains.telemetry.models import TelemetryEventRecord
from scripts.nightly_export import (
    JOB_NAME,
    export_telemetry_to_csv,
    main,
    resolve_target_date,
)


@pytest.fixture
def test_engine():
    """Provides an isolated in-memory SQLite engine with job_runs and telemetry tables."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    init_db(bind_engine=engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


# --- 1. Date Resolution Tests ---

def test_resolve_target_date_explicit_argument() -> None:
    resolved = resolve_target_date("2026-09-21")
    assert resolved == date(2026, 9, 21)


def test_resolve_target_date_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TARGET_DATE", "2026-09-18")
    resolved = resolve_target_date(None)
    assert resolved == date(2026, 9, 18)


def test_resolve_target_date_default_yesterday_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TARGET_DATE", raising=False)
    resolved = resolve_target_date(None)
    yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
    assert resolved == yesterday


def test_resolve_target_date_invalid_format() -> None:
    with pytest.raises(ValueError, match="Invalid date format"):
        resolve_target_date("2026/09/21")


# --- 2. CSV Export Filtering Tests ---

def test_export_telemetry_to_csv_filters_strictly_by_day(
    test_engine,
    tmp_path: Path,
) -> None:
    target = date(2026, 9, 21)

    # Populate events across 3 days:
    events = [
        # Prior day: 2026-09-20 23:59:59 UTC -> must be excluded
        TelemetryEventRecord(
            event_id=uuid.uuid4(),
            event_type="inbound_order_created",
            timestamp=datetime(2026, 9, 20, 23, 59, 59, tzinfo=timezone.utc),
            service="backoffice",
            session_id="sess-prev",
            user_id=uuid.uuid4(),
            request_id="req-prev",
            tags={"local_id": "MED-001", "quantity": 10},
        ),
        # Target day start: 2026-09-21 00:00:00 UTC -> must be included
        TelemetryEventRecord(
            event_id=uuid.uuid4(),
            event_type="outbound_order_created",
            timestamp=datetime(2026, 9, 21, 0, 0, 0, tzinfo=timezone.utc),
            service="backoffice",
            session_id="sess-target-1",
            user_id=uuid.uuid4(),
            request_id="req-target-1",
            tags={"local_id": "MED-001", "quantity": 5},
        ),
        # Target day midday: 2026-09-21 14:30:00 UTC -> must be included
        TelemetryEventRecord(
            event_id=uuid.uuid4(),
            event_type="outbound_insufficient_stock_attempted",
            timestamp=datetime(2026, 9, 21, 14, 30, 0, tzinfo=timezone.utc),
            service="backoffice",
            session_id="sess-target-2",
            user_id=uuid.uuid4(),
            request_id="req-target-2",
            tags={"local_id": "MIA-001", "requested_quantity": 20},
        ),
        # Target day end: 2026-09-21 23:59:59 UTC -> must be included
        TelemetryEventRecord(
            event_id=uuid.uuid4(),
            event_type="inbound_order_created",
            timestamp=datetime(2026, 9, 21, 23, 59, 59, tzinfo=timezone.utc),
            service="backoffice",
            session_id="sess-target-3",
            user_id=uuid.uuid4(),
            request_id="req-target-3",
            tags={"local_id": "MIA-001", "quantity": 15},
        ),
        # Next day start: 2026-09-22 00:00:00 UTC -> must be excluded
        TelemetryEventRecord(
            event_id=uuid.uuid4(),
            event_type="form_abandoned",
            timestamp=datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc),
            service="backoffice",
            session_id="sess-next",
            user_id=uuid.uuid4(),
            request_id="req-next",
            tags={"form_name": "inbound"},
        ),
    ]

    with Session(test_engine) as session:
        session.add_all(events)
        session.commit()

    csv_path, count, is_new = export_telemetry_to_csv(
        engine=test_engine,
        target_date=target,
        output_dir=tmp_path,
    )

    assert is_new is True
    assert count == 3
    assert csv_path.exists()
    assert csv_path.name == "telemetry_2026-09-21.csv"

    # Verify CSV rows
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        assert len(reader) == 3
        # Ensure only target date events
        for row in reader:
            assert row["timestamp"].startswith("2026-09-21")
            parsed_tags = json.loads(row["tags"])
            assert isinstance(parsed_tags, dict)


def test_export_telemetry_to_csv_preserves_existing_file(
    test_engine,
    tmp_path: Path,
) -> None:
    target = date(2026, 9, 21)
    existing_file = tmp_path / "telemetry_2026-09-21.csv"
    existing_content = "event_id,event_type\nPRE_EXISTING_DATA,custom\n"
    existing_file.write_text(existing_content, encoding="utf-8")

    csv_path, count, is_new = export_telemetry_to_csv(
        engine=test_engine,
        target_date=target,
        output_dir=tmp_path,
    )

    assert is_new is False
    assert count == 0
    assert csv_path == existing_file
    # File must NOT have been overwritten
    assert csv_path.read_text(encoding="utf-8") == existing_content


# --- 3. Atomic Claiming & Lifecycle Tests ---

def test_claim_job_run_already_completed(test_engine) -> None:
    target = date(2026, 9, 21)
    with Session(test_engine) as session:
        completed = JobRunRecord(
            job_name=JOB_NAME,
            target_date=target,
            status="completed",
            started_at=datetime.now(timezone.utc) - timedelta(hours=1),
            finished_at=datetime.now(timezone.utc) - timedelta(minutes=50),
        )
        session.add(completed)
        session.commit()

    with Session(test_engine) as session:
        claimed, status = claim_job_run(session, JOB_NAME, target)
        assert status == "ALREADY_COMPLETED"
        assert claimed is not None
        assert claimed.status == "completed"

    # Ensure no additional rows were created
    with Session(test_engine) as session:
        runs = session.exec(select(JobRunRecord)).all()
        assert len(runs) == 1


def test_claim_job_run_retries_after_failure(test_engine) -> None:
    target = date(2026, 9, 21)
    with Session(test_engine) as session:
        failed = JobRunRecord(
            job_name=JOB_NAME,
            target_date=target,
            status="failed",
            started_at=datetime.now(timezone.utc) - timedelta(hours=2),
            finished_at=datetime.now(timezone.utc) - timedelta(hours=2),
            error_message="Subprocess crashed earlier",
        )
        session.add(failed)
        session.commit()

    # Retry claim
    with Session(test_engine) as session:
        claimed, status = claim_job_run(session, JOB_NAME, target)
        assert status == "CLAIMED"
        assert claimed is not None
        assert claimed.status == "processing"
        run_id = claimed.id

    # Complete it
    with Session(test_engine) as session:
        completed = complete_job_run(session, run_id)
        assert completed.status == "completed"
        assert completed.finished_at is not None

    with Session(test_engine) as session:
        runs = session.exec(select(JobRunRecord).order_by(JobRunRecord.created_at.asc())).all()
        assert len(runs) == 2
        assert runs[0].status == "failed"
        assert runs[1].status == "completed"


def test_claim_job_run_recovers_stale_processing(test_engine) -> None:
    target = date(2026, 9, 21)
    three_hours_ago = datetime.now(timezone.utc) - timedelta(hours=3)

    with Session(test_engine) as session:
        stale_run = JobRunRecord(
            job_name=JOB_NAME,
            target_date=target,
            status="processing",
            started_at=three_hours_ago,
        )
        session.add(stale_run)
        session.commit()
        stale_id = stale_run.id

    # Claim with 60 min stale timeout -> must recover stale run as failed and claim a new one
    with Session(test_engine) as session:
        claimed, status = claim_job_run(
            session=session,
            job_name=JOB_NAME,
            target_date=target,
            stale_timeout_minutes=60,
        )
        assert status == "CLAIMED"
        assert claimed is not None
        assert claimed.id != stale_id
        assert claimed.status == "processing"

    with Session(test_engine) as session:
        old = session.get(JobRunRecord, stale_id)
        assert old.status == "failed"
        assert "Stale processing run recovered" in (old.error_message or "")


def test_concurrency_blocks_simultaneous_processing(test_engine) -> None:
    target = date(2026, 9, 21)

    # First claim succeeds
    with Session(test_engine) as session1:
        run1, status1 = claim_job_run(session1, JOB_NAME, target)
        assert status1 == "CLAIMED"
        assert run1 is not None

    # Second claim during active processing is blocked
    with Session(test_engine) as session2:
        run2, status2 = claim_job_run(session2, JOB_NAME, target, stale_timeout_minutes=60)
        assert status2 == "CONCURRENT_PROCESSING"
        assert run2 is None


# --- 4. End-to-End CLI Invocation Tests ---

def test_nightly_export_cli_success(test_engine, tmp_path: Path) -> None:
    target = "2026-09-21"
    db_url = "sqlite:///:memory:"

    # Patch create_engine to use our initialized test_engine
    with patch("scripts.nightly_export.create_engine", return_value=test_engine):
        with patch("scripts.nightly_export.run_pipeline_subprocess") as mock_subproc:
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=["pipeline.py"],
                returncode=0,
                stdout="BRASALAND INVENTORY HEALTH PIPELINE — RUN SUMMARY\nStatus:              COMPLETED\n",
                stderr="",
            )

            exit_code = main(
                [
                    "--target-date",
                    target,
                    "--db-url",
                    db_url,
                    "--output-dir",
                    str(tmp_path),
                ]
            )

            assert exit_code == 0
            assert mock_subproc.called

    with Session(test_engine) as session:
        run = session.exec(select(JobRunRecord).where(JobRunRecord.target_date == date(2026, 9, 21))).first()
        assert run is not None
        assert run.status == "completed"
        assert run.finished_at is not None


def test_nightly_export_cli_pipeline_skipped_marks_failed(test_engine, tmp_path: Path) -> None:
    target = "2026-09-22"
    db_url = "sqlite:///:memory:"

    with patch("scripts.nightly_export.create_engine", return_value=test_engine):
        with patch("scripts.nightly_export.run_pipeline_subprocess") as mock_subproc:
            # Child pipeline was SKIPPED due to lock (exit code 2)
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=["pipeline.py"],
                returncode=2,
                stdout="BRASALAND INVENTORY HEALTH PIPELINE — RUN SUMMARY\nStatus:              SKIPPED\n",
                stderr="",
            )

            exit_code = main(
                [
                    "--target-date",
                    target,
                    "--db-url",
                    db_url,
                    "--output-dir",
                    str(tmp_path),
                ]
            )

            assert exit_code == 1

    with Session(test_engine) as session:
        run = session.exec(select(JobRunRecord).where(JobRunRecord.target_date == date(2026, 9, 22))).first()
        assert run is not None
        # MUST be failed, NOT completed!
        assert run.status == "failed"
        assert "SKIPPED due to active concurrency lock" in (run.error_message or "")


def test_nightly_export_cli_pipeline_failure_marks_failed(test_engine, tmp_path: Path) -> None:
    target = "2026-09-23"
    db_url = "sqlite:///:memory:"

    with patch("scripts.nightly_export.create_engine", return_value=test_engine):
        with patch("scripts.nightly_export.run_pipeline_subprocess") as mock_subproc:
            mock_subproc.return_value = subprocess.CompletedProcess(
                args=["pipeline.py"],
                returncode=1,
                stdout="",
                stderr="Fatal error: Database connection refused",
            )

            exit_code = main(
                [
                    "--target-date",
                    target,
                    "--db-url",
                    db_url,
                    "--output-dir",
                    str(tmp_path),
                ]
            )

            assert exit_code == 1

    with Session(test_engine) as session:
        run = session.exec(select(JobRunRecord).where(JobRunRecord.target_date == date(2026, 9, 23))).first()
        assert run is not None
        assert run.status == "failed"
        assert "Database connection refused" in (run.error_message or "")


def test_nightly_export_cli_idempotent_skip_on_completed(test_engine, tmp_path: Path) -> None:
    target = "2026-09-24"
    db_url = "sqlite:///:memory:"

    # Pre-populate completed record
    with Session(test_engine) as session:
        session.add(
            JobRunRecord(
                job_name=JOB_NAME,
                target_date=date(2026, 9, 24),
                status="completed",
                started_at=datetime.now(timezone.utc) - timedelta(hours=1),
                finished_at=datetime.now(timezone.utc) - timedelta(minutes=50),
            )
        )
        session.commit()

    with patch("scripts.nightly_export.create_engine", return_value=test_engine):
        with patch("scripts.nightly_export.run_pipeline_subprocess") as mock_subproc:
            exit_code = main(
                [
                    "--target-date",
                    target,
                    "--db-url",
                    db_url,
                    "--output-dir",
                    str(tmp_path),
                ]
            )

            # Idempotent skip returns exit code 0 without running pipeline
            assert exit_code == 0
            assert not mock_subproc.called
