#!/usr/bin/env python3
"""
nightly_export.py — Brasaland · Nightly Telemetry Backup & Business Pipeline Runner

Performs the scheduled nightly orchestration (ticket #DEV-53):
1. Atomically claims the execution for TARGET_DATE in the `job_runs` table.
2. Exports telemetry events for TARGET_DATE (UTC) into data/raw/telemetry_YYYY-MM-DD.csv
   as an immutable, idempotent backup (never overwrites if already present).
3. Invokes the real business performance pipeline (data/pipelines/pipeline.py) as a subprocess,
   distinguishing strictly between COMPLETED (success) and SKIPPED (concurrency lock).
4. Records final lifecycle transitions (pending -> processing -> completed / failed) in `job_runs`.

Scheduling (Cron):
    Expression: 0 3 * * * (03:00 UTC daily, 22:00 COT/EST store close)
    Command:    uv run --project services/api python scripts/nightly_export.py
    Environment: DATABASE_URL

Usage:
    python scripts/nightly_export.py [--target-date YYYY-MM-DD] [--db-url URL] [--full-reconciliation]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Sequence

# Ensure monorepo root and services/api are on sys.path
repo_root = Path(__file__).resolve().parent.parent
services_api_path = repo_root / "services" / "api"
if str(services_api_path) not in sys.path:
    sys.path.insert(0, str(services_api_path))
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from app.domains.jobs.service import (
    claim_job_run,
    complete_job_run,
    fail_job_run,
)
from app.domains.telemetry.models import TelemetryEventRecord

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nightly_export")

JOB_NAME = "telemetry_nightly_export"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Brasaland Nightly Telemetry Export and Pipeline Runner (#DEV-53)"
    )
    parser.add_argument(
        "--target-date",
        type=str,
        default=None,
        help="Target date YYYY-MM-DD (defaults to TARGET_DATE env var, or yesterday in UTC).",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="Database URL (defaults to DATABASE_URL or TEST_DATABASE_URL environment variable).",
    )
    parser.add_argument(
        "--stale-timeout-minutes",
        type=int,
        default=60,
        help="Timeout in minutes after which an active 'processing' run is considered stale (default: 60).",
    )
    parser.add_argument(
        "--full-reconciliation",
        action="store_true",
        default=False,
        help="Pass --full-reconciliation to the underlying business pipeline.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to store CSV backups (defaults to data/raw).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable debug logging output.",
    )
    return parser.parse_args(argv)


def resolve_target_date(date_str: Optional[str]) -> date:
    """Resolves target date from CLI argument, env var, or defaults to yesterday UTC."""
    raw_date = date_str or os.environ.get("TARGET_DATE")
    if raw_date:
        try:
            return datetime.strptime(raw_date.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(
                f"Invalid date format for TARGET_DATE: '{raw_date}'. Expected YYYY-MM-DD."
            ) from exc
    # Default: yesterday in UTC
    yesterday_utc = datetime.now(timezone.utc).date() - timedelta(days=1)
    return yesterday_utc


def resolve_database_url(cli_url: Optional[str]) -> str:
    """Resolves database URL from argument or environment variables without logging credentials."""
    url = cli_url or os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Database URL is not configured. Please supply --db-url or set DATABASE_URL."
        )
    return url


def export_telemetry_to_csv(
    engine,
    target_date: date,
    output_dir: Path,
) -> tuple[Path, int, bool]:
    """
    Exports telemetry events for target_date (UTC) into a CSV backup file.
    Does NOT overwrite if the file already exists (idempotent).
    Uses streaming and atomic file replacement via temporary file.

    Returns:
        (csv_path, row_count, is_newly_created)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"telemetry_{target_date.strftime('%Y-%m-%d')}.csv"
    csv_path = output_dir / filename

    if csv_path.exists():
        logger.info(
            "Backup CSV file already exists at %s. Skipping CSV export to preserve historical backup.",
            csv_path,
        )
        return csv_path, 0, False

    start_utc = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=1)

    temp_path = output_dir / f"{filename}.tmp.{os.getpid()}"

    query = (
        select(TelemetryEventRecord)
        .where(
            TelemetryEventRecord.timestamp >= start_utc,
            TelemetryEventRecord.timestamp < end_utc,
        )
        .order_by(TelemetryEventRecord.timestamp.asc())
    )

    fieldnames = [
        "event_id",
        "event_type",
        "timestamp",
        "service",
        "session_id",
        "user_id",
        "request_id",
        "tags",
    ]

    row_count = 0
    with Session(engine) as session:
        events = session.exec(query)
        with open(temp_path, mode="w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for event in events:
                tags_json = json.dumps(event.tags or {}, ensure_ascii=False)
                writer.writerow(
                    {
                        "event_id": str(event.event_id),
                        "event_type": event.event_type,
                        "timestamp": event.timestamp.isoformat() if event.timestamp else "",
                        "service": event.service,
                        "session_id": event.session_id or "",
                        "user_id": str(event.user_id) if event.user_id else "",
                        "request_id": event.request_id,
                        "tags": tags_json,
                    }
                )
                row_count += 1

    # Atomic rename/replace to ensure no partial files exist
    os.replace(temp_path, csv_path)
    logger.info(
        "Successfully exported %d telemetry events to backup CSV: %s",
        row_count,
        csv_path,
    )
    return csv_path, row_count, True


def run_pipeline_subprocess(
    db_url: str,
    full_reconciliation: bool = False,
) -> subprocess.CompletedProcess[str]:
    """
    Executes data/pipelines/pipeline.py as a clean subprocess.
    Preserves child environment and forwards database URL securely.
    """
    pipeline_script = repo_root / "data" / "pipelines" / "pipeline.py"
    cmd = [sys.executable, str(pipeline_script)]

    if full_reconciliation:
        cmd.append("--full-reconciliation")
    if db_url:
        cmd.extend(["--db-url", db_url])

    env = dict(os.environ)
    env["DATABASE_URL"] = db_url

    logger.info("Spawning business pipeline subprocess: %s", pipeline_script)
    proc = subprocess.run(
        cmd,
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        target_date = resolve_target_date(args.target_date)
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    try:
        db_url = resolve_database_url(args.db_url)
    except RuntimeError as exc:
        logger.error("Configuration error: %s", exc)
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else (repo_root / "data" / "raw")

    logger.info("============================================================")
    logger.info("BRASALAND NIGHTLY TELEMETRY & PIPELINE ORCHESTRATION (#DEV-53)")
    logger.info("Target Date:   %s", target_date)
    logger.info("Output Dir:    %s", output_dir)
    logger.info("Reconcile:     %s", "FULL" if args.full_reconciliation else "INCREMENTAL")
    logger.info("============================================================")

    engine = create_engine(db_url, pool_pre_ping=True)

    # Step 1: Atomically claim job run
    with Session(engine) as session:
        claimed_run, claim_status = claim_job_run(
            session=session,
            job_name=JOB_NAME,
            target_date=target_date,
            stale_timeout_minutes=args.stale_timeout_minutes,
        )

    if claim_status == "ALREADY_COMPLETED":
        logger.info(
            "Target date %s already has a COMPLETED execution (job_run_id=%s). Omitting run.",
            target_date,
            claimed_run.id if claimed_run else "unknown",
        )
        return 0

    if claim_status == "CONCURRENT_PROCESSING":
        logger.warning(
            "Target date %s is currently active under another processing run. Aborting concurrent attempt.",
            target_date,
        )
        return 1

    run_id = claimed_run.id
    logger.info("Claimed job execution %s in 'processing' state.", run_id)
    start_time = time.monotonic()

    # Step 2: Export CSV backup
    try:
        csv_path, exported_count, is_new = export_telemetry_to_csv(
            engine=engine,
            target_date=target_date,
            output_dir=output_dir,
        )
    except Exception as exc:
        err_msg = f"Failed to export telemetry CSV backup: {exc}"
        logger.exception(err_msg)
        with Session(engine) as session:
            fail_job_run(session, run_id, err_msg)
        return 1

    # Step 3: Run pipeline as subprocess
    try:
        proc = run_pipeline_subprocess(
            db_url=db_url,
            full_reconciliation=args.full_reconciliation,
        )
    except Exception as exc:
        err_msg = f"Failed to spawn pipeline subprocess: {exc}"
        logger.exception(err_msg)
        with Session(engine) as session:
            fail_job_run(session, run_id, err_msg)
        return 1

    elapsed_duration = time.monotonic() - start_time

    # Step 4: Verify subprocess outcome
    stdout_summary = proc.stdout or ""
    stderr_summary = proc.stderr or ""

    if proc.returncode == 0 and "Status:              COMPLETED" in stdout_summary:
        logger.info(
            "Business pipeline subprocess completed successfully in %.2fs.",
            elapsed_duration,
        )
        with Session(engine) as session:
            complete_job_run(session, run_id)

        print("\n" + "=" * 60)
        print("NIGHTLY ORCHESTRATION COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"Job Run ID:        {run_id}")
        print(f"Job Name:          {JOB_NAME}")
        print(f"Target Date:       {target_date}")
        print(f"Status:            COMPLETED")
        print(f"Backup CSV:        {csv_path} ({'new' if is_new else 'existing'})")
        print(f"Events Exported:   {exported_count}")
        print(f"Duration:          {elapsed_duration:.2f}s")
        print("=" * 60 + "\n")
        return 0

    elif proc.returncode == 2 or "Status:              SKIPPED" in stdout_summary:
        err_msg = "Child business pipeline was SKIPPED due to active concurrency lock."
        logger.error(err_msg)
        with Session(engine) as session:
            fail_job_run(session, run_id, err_msg)

        print("\n" + "=" * 60)
        print("NIGHTLY ORCHESTRATION FINISHED WITH FAILURE (SKIPPED)")
        print("=" * 60)
        print(f"Job Run ID:        {run_id}")
        print(f"Target Date:       {target_date}")
        print(f"Status:            FAILED")
        print(f"Detail:            {err_msg}")
        print("=" * 60 + "\n")
        return 1

    else:
        err_detail = (
            stderr_summary.strip()
            if stderr_summary.strip()
            else stdout_summary[-500:].strip()
        )
        err_msg = f"Child pipeline returned code {proc.returncode}: {err_detail}"
        logger.error(err_msg)
        with Session(engine) as session:
            fail_job_run(session, run_id, err_msg)

        print("\n" + "=" * 60)
        print("NIGHTLY ORCHESTRATION FAILED")
        print("=" * 60)
        print(f"Job Run ID:        {run_id}")
        print(f"Target Date:       {target_date}")
        print(f"Status:            FAILED")
        print(f"Detail:            {err_msg}")
        print("=" * 60 + "\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
