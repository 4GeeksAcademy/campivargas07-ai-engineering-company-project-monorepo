"""
service.py — Brasaland · Business logic layer for Reporting Domain

Orchestrates manual execution triggers, run status checks, and business KPI queries.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.domains.reporting.repository import ReportingRepository
from data.pipelines.inventory_health.flow import trigger_inventory_health_flow
from app.domains.tasks.repository import TaskRepository
from app.worker.inventory_health import run_inventory_health

logger = logging.getLogger("reporting_service")


class ReportingService:
    def __init__(self, repository: Optional[ReportingRepository] = None):
        self.repository = repository or ReportingRepository()

    def trigger_run(
        self,
        current_user: dict[str, Any],
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
        flow_run_id = None
        task_repository = TaskRepository(self.repository.engine)
        try:
            enqueue_info = trigger_inventory_health_flow(triggered_by=user_uuid)
            flow_run_id = enqueue_info["flow_run_id"]
            task_repository.register(flow_run_id)
            run_inventory_health.apply_async(args=[flow_run_id], task_id=flow_run_id, retry=False)
        except Exception:
            if flow_run_id:
                try:
                    task_repository.failed(flow_run_id, "Task publication failed", 0, dead_letter=False)
                except Exception:
                    logger.error("task_id=%s status=publication_cleanup_failure", flow_run_id)
            logger.error("task_id=%s attempt=0 status=publication_failure", flow_run_id)
            raise HTTPException(503, "Inventory health task could not be queued") from None
        enqueue_info["task_id"] = flow_run_id
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
