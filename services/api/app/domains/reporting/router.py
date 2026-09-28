"""
router.py — Brasaland · FastAPI router for Reporting Domain

Endpoints:
- POST /reporting/inventory-health/runs (HTTP 202 Accepted)
- GET /reporting/inventory-health/runs/{flow_run_id} (HTTP 200 OK)
- GET /reporting/inventory-health (HTTP 200 OK)
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.domains.auth.dependencies import get_current_user
from app.domains.reporting.schemas import (
    InventoryHealthResponse,
    PipelineRunStatusResponse,
    PipelineRunTriggerResponse,
)
from app.domains.reporting.service import ReportingService, _run_pipeline_background

# Explicit canonical imports designed in PIPELINE_DESIGN.md section 17.2
from data.pipelines.inventory_health.flow import (
    get_pipeline_run_status,
    trigger_inventory_health_flow,
)
from data.pipelines.inventory_health.queries import fetch_inventory_health_snapshot

router = APIRouter(prefix="/reporting", tags=["reporting"])


def get_reporting_service() -> ReportingService:
    return ReportingService()


@router.post(
    "/inventory-health/runs",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PipelineRunTriggerResponse,
    summary="Trigger Inventory Health Pipeline Run",
    description="Enqueues an asynchronous inventory health pipeline run. Requires admin or manager role.",
)
def trigger_pipeline_run(
    background_tasks: BackgroundTasks,
    current_user: dict[str, Any] = Depends(get_current_user),
    service: ReportingService = Depends(get_reporting_service),
) -> PipelineRunTriggerResponse:
    """
    Despacha la ejecución en Prefect asignando un flow_run_id y encolando la tarea sin bloquear la petición.
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

    # Asynchronous non-blocking execution via BackgroundTasks
    background_tasks.add_task(_run_pipeline_background, flow_run_id)

    return PipelineRunTriggerResponse(**enqueue_info)


@router.get(
    "/inventory-health/runs/{flow_run_id}",
    response_model=PipelineRunStatusResponse,
    summary="Get Pipeline Run Status",
    description="Queries execution status, timestamps, duration, and counters for a specific run or 'latest'.",
)
def get_run_status_endpoint(
    flow_run_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
    service: ReportingService = Depends(get_reporting_service),
) -> PipelineRunStatusResponse:
    """
    Consulta el estado y contadores de la corrida en reporting.pipeline_execution_logs.
    """
    status_info = service.get_run_status(flow_run_id)
    return PipelineRunStatusResponse(**status_info)


@router.get(
    "/inventory-health",
    response_model=InventoryHealthResponse,
    summary="Get Inventory Health Business KPIs",
    description="Provides consolidated inventory health snapshot and KPIs for the business dashboard.",
)
def get_inventory_health_endpoint(
    date: Optional[str] = Query(None, description="Snapshot date (YYYY-MM-DD), defaults to latest available"),
    local_id: Optional[str] = Query(None, description="Filter by location identifier (e.g. MED-001)"),
    ingredient_id: Optional[UUID] = Query(None, description="Filter by ingredient UUID"),
    only_critical: bool = Query(False, description="Filter to only critical items (stockout or below minimum)"),
    current_user: dict[str, Any] = Depends(get_current_user),
    service: ReportingService = Depends(get_reporting_service),
) -> InventoryHealthResponse:
    """
    Ejecuta la consulta analítica optimizada sobre reporting.inventory_health_snapshot aplicando agregados y filtros.
    """
    data = service.get_inventory_health(
        date=date,
        local_id=local_id,
        ingredient_id=ingredient_id,
        only_critical=only_critical,
    )
    return InventoryHealthResponse(**data)
