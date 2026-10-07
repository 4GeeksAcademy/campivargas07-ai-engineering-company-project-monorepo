"""
repository.py — Brasaland · Data access layer for Reporting Domain

Connects FastAPI reporting endpoints to the authoritative query functions in data/pipelines/inventory_health/queries.py.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from app.database import get_db_engine
from data.pipelines.inventory_health.queries import (
    fetch_inventory_health_snapshot as _fetch_snapshot,
    get_pipeline_run_status as _get_run_status,
    record_execution_start as _record_execution_start,
)


import os
from sqlalchemy import create_engine

class ReportingRepository:
    def __init__(self, engine=None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is not None:
            return self._engine
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
        if db_url:
            return create_engine(db_url, pool_pre_ping=True)
        return get_db_engine()

    def get_run_status(self, flow_run_id: str = "latest") -> Optional[dict[str, Any]]:
        """Queries reporting.pipeline_execution_logs by run UUID or 'latest'."""
        return _get_run_status(self.engine, flow_run_id=flow_run_id)

    def record_run_start(
        self,
        pipeline_run_id: UUID,
        status: str = "SCHEDULED",
    ) -> None:
        """Records initial execution state."""
        _record_execution_start(self.engine, pipeline_run_id, status=status)

    def get_inventory_health(
        self,
        date: Optional[str] = None,
        local_id: Optional[str] = None,
        ingredient_id: Optional[UUID | str] = None,
        only_critical: bool = False,
    ) -> dict[str, Any]:
        """Queries reporting.inventory_health_snapshot with filters."""
        return _fetch_snapshot(
            self.engine,
            date=date,
            local_id=local_id,
            ingredient_id=ingredient_id,
            only_critical=only_critical,
        )
