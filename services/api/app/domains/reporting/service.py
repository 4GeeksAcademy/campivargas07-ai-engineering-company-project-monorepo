"""
service.py — Brasaland · Business logic layer for Reporting Domain

Orchestrates manual execution triggers, run status checks, and business KPI queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status

from app.domains.reporting.repository import ReportingRepository
from data.pipelines.inventory_health.flow import (
    inventory_health_business_flow,
    trigger_inventory_health_flow,
)

logger = logging.getLogger("reporting_service")


def _run_pipeline_background(flow_run_id: str) -> None:
    """Target worker function executed in the background by FastAPI BackgroundTasks."""
    try:
        logger.info("Executing background inventory health pipeline run %s...", flow_run_id)
        result = inventory_health_business_flow(run_id=flow_run_id)
        logger.info("Background run %s completed with status: %s", flow_run_id, result.get("status"))
    except Exception as exc:
        logger.error("Background run %s failed with exception: %s", flow_run_id, exc)


class ReportingService:
    def __init__(self, repository: Optional[ReportingRepository] = None):
        self.repository = repository or ReportingRepository()

    def trigger_run(
        self,
        current_user: dict[str, Any],
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        """
        Enqueues an asynchronous inventory health pipeline run.
        Authorizes callers with admin or manager roles.
        """
        caller_role = current_user.get("role", "user")
        if caller_role not in {"admin", "manager"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: User lacks operational permissions to trigger pipeline runs.",
            )

        user_uuid = current_user.get("uuid") or str(current_user.get("id"))
        enqueue_info = trigger_inventory_health_flow(triggered_by=user_uuid)
        flow_run_id = enqueue_info["flow_run_id"]

        # Enqueue background execution without blocking HTTP response
        background_tasks.add_task(_run_pipeline_background, flow_run_id)

        return enqueue_info

    def get_run_status(self, flow_run_id: str) -> dict[str, Any]:
        """
        Fetches status, duration, counters, and sanitized errors of a flow run.
        Raises HTTP 404 if not found.
        """
        status_info = self.repository.get_run_status(flow_run_id=flow_run_id)
        if status_info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pipeline run '{flow_run_id}' not found.",
            )
        return status_info

    def get_inventory_health(
        self,
        date: Optional[str] = None,
        local_id: Optional[str] = None,
        ingredient_id: Optional[UUID | str] = None,
        only_critical: bool = False,
    ) -> dict[str, Any]:
        """
        Returns authoritative inventory health snapshot KPIs and line items.
        """
        return self.repository.get_inventory_health(
            date=date,
            local_id=local_id,
            ingredient_id=ingredient_id,
            only_critical=only_critical,
        )
