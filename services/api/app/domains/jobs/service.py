"""
service.py — Brasaland · Job runs service with atomic claiming and lifecycle management.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.domains.jobs.models import JobRunRecord

logger = logging.getLogger("jobs_service")


def claim_job_run(
    session: Session,
    job_name: str,
    target_date: date,
    stale_timeout_minutes: int = 60,
) -> Tuple[Optional[JobRunRecord], str]:
    """
    Atomically claims a job run execution for a given (job_name, target_date).

    Returns:
        (job_run, "CLAIMED"): Successfully claimed and set to 'processing'.
        (existing_run, "ALREADY_COMPLETED"): Target date was already completed.
        (None, "CONCURRENT_PROCESSING"): Another active process is currently running.
    """
    now = datetime.now(timezone.utc)

    # 1. Check if an execution has already completed successfully
    completed_stmt = (
        select(JobRunRecord)
        .where(
            JobRunRecord.job_name == job_name,
            JobRunRecord.target_date == target_date,
            JobRunRecord.status == "completed",
        )
        .limit(1)
    )
    completed_run = session.exec(completed_stmt).first()
    if completed_run:
        logger.info(
            "Job '%s' for target date %s is already completed (run_id=%s). Skipping.",
            job_name,
            target_date,
            completed_run.id,
        )
        return completed_run, "ALREADY_COMPLETED"

    # 2. Check if an execution is currently in 'processing' state
    processing_stmt = (
        select(JobRunRecord)
        .where(
            JobRunRecord.job_name == job_name,
            JobRunRecord.target_date == target_date,
            JobRunRecord.status == "processing",
        )
        .with_for_update()
    )
    processing_run = session.exec(processing_stmt).first()

    if processing_run:
        # Check if the processing run is stale (interrupted / killed abruptly)
        started_at = processing_run.started_at
        if started_at is not None:
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            elapsed_seconds = (now - started_at).total_seconds()
        else:
            elapsed_seconds = float("inf")

        if elapsed_seconds >= (stale_timeout_minutes * 60):
            logger.warning(
                "Found stale processing run %s for job '%s' date %s (elapsed %.1fs >= %ds). "
                "Marking as failed and recovering.",
                processing_run.id,
                job_name,
                target_date,
                elapsed_seconds,
                stale_timeout_minutes * 60,
            )
            processing_run.status = "failed"
            processing_run.finished_at = now
            processing_run.error_message = (
                f"Stale processing run recovered after {stale_timeout_minutes}m timeout"
            )
            session.add(processing_run)
            session.commit()
            # Stale run has been marked failed; we can now proceed to claim a new run below
        else:
            logger.warning(
                "Job '%s' for target date %s is currently being processed by run %s (elapsed %.1fs).",
                job_name,
                target_date,
                processing_run.id,
                elapsed_seconds,
            )
            return None, "CONCURRENT_PROCESSING"

    # 3. Check if there is an existing pending run to transition
    pending_stmt = (
        select(JobRunRecord)
        .where(
            JobRunRecord.job_name == job_name,
            JobRunRecord.target_date == target_date,
            JobRunRecord.status == "pending",
        )
        .with_for_update()
        .limit(1)
    )
    pending_run = session.exec(pending_stmt).first()

    if pending_run:
        pending_run.status = "processing"
        pending_run.started_at = now
        session.add(pending_run)
        try:
            session.commit()
            session.refresh(pending_run)
            logger.info(
                "Transitioned pending job run %s for '%s' (%s) to 'processing'.",
                pending_run.id,
                job_name,
                target_date,
            )
            return pending_run, "CLAIMED"
        except IntegrityError:
            session.rollback()
            logger.warning(
                "Concurrent claim conflict for pending job '%s' on %s.",
                job_name,
                target_date,
            )
            return None, "CONCURRENT_PROCESSING"

    # 4. Create a new run record directly in 'processing' state
    new_run = JobRunRecord(
        job_name=job_name,
        target_date=target_date,
        status="processing",
        started_at=now,
    )
    session.add(new_run)
    try:
        session.commit()
        session.refresh(new_run)
        logger.info(
            "Claimed new job run %s for '%s' (%s) in 'processing' state.",
            new_run.id,
            job_name,
            target_date,
        )
        return new_run, "CLAIMED"
    except IntegrityError:
        session.rollback()
        logger.warning(
            "Concurrent claim conflict when creating new run for '%s' on %s.",
            job_name,
            target_date,
        )
        return None, "CONCURRENT_PROCESSING"


def complete_job_run(session: Session, run_id: UUID) -> JobRunRecord:
    """Marks a job run as completed with current timestamp."""
    run = session.get(JobRunRecord, run_id)
    if not run:
        raise ValueError(f"Job run {run_id} not found")
    run.status = "completed"
    run.finished_at = datetime.now(timezone.utc)
    session.add(run)
    session.commit()
    session.refresh(run)
    logger.info("Job run %s marked as 'completed'.", run_id)
    return run


def fail_job_run(
    session: Session,
    run_id: UUID,
    error_message: str,
) -> JobRunRecord:
    """Marks a job run as failed with error detail and current timestamp."""
    run = session.get(JobRunRecord, run_id)
    if not run:
        raise ValueError(f"Job run {run_id} not found")
    run.status = "failed"
    run.finished_at = datetime.now(timezone.utc)
    run.error_message = error_message
    session.add(run)
    session.commit()
    session.refresh(run)
    logger.error("Job run %s marked as 'failed': %s", run_id, error_message)
    return run
