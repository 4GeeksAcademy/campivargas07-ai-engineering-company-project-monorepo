"""
schemas.py — Brasaland · Pydantic V2 schemas for Reporting Domain

Data transfer objects for:
- POST /reporting/inventory-health/runs (PipelineRunTriggerResponse)
- GET /reporting/inventory-health/runs/{flow_run_id} (PipelineRunStatusResponse)
- GET /reporting/inventory-health (InventoryHealthResponse)
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PipelineRunTriggerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow_run_id: str = Field(..., description="Unique UUID for this pipeline execution")
    status: str = Field(..., description="Initial execution state (e.g. SCHEDULED)")
    enqueued_at: str = Field(..., description="UTC ISO 8601 timestamp when run was enqueued")
    triggered_by: Optional[str] = Field(default=None, description="UUID of user who triggered the run")
    message: str = Field(..., description="Operational status message")


class PipelineRunCounters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_events_read: int = Field(default=0, description="Total source events read from telemetry")
    records_quarantined: int = Field(default=0, description="Total events routed to quarantine")


class PipelineRunStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flow_run_id: str = Field(..., description="Execution run identifier")
    status: str = Field(..., description="Run status: SCHEDULED, RUNNING, COMPLETED, FAILED, SKIPPED")
    started_at: Optional[str] = Field(default=None, description="UTC start timestamp")
    completed_at: Optional[str] = Field(default=None, description="UTC completion timestamp")
    duration_seconds: Optional[float] = Field(default=None, description="Total execution duration in seconds")
    counters: PipelineRunCounters = Field(default_factory=PipelineRunCounters)
    error_message: Optional[str] = Field(default=None, description="Sanitized error description if failed")


class InventoryHealthPeriod(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_date: str = Field(..., description="Snapshot date (YYYY-MM-DD)")
    data_freshness_timestamp: Optional[str] = Field(default=None, description="Latest computed_at timestamp in snapshot")
    freshness_lag_seconds: Optional[int] = Field(default=None, description="Lag in seconds relative to current time")


class InventoryHealthSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_locations_reported: int = Field(..., description="Count of distinct locations reporting")
    total_ingredients_monitored: int = Field(..., description="Count of distinct ingredients monitored")
    critical_stockouts_count: int = Field(..., description="Count of items currently with stockout (<= 0)")
    below_minimum_count: int = Field(..., description="Count of items below minimum stock")
    average_stock_level_ratio: float = Field(..., description="Mean ratio of current_stock / minimum_stock")
    insufficient_stock_attempts_count: int = Field(..., description="Sum of blocked outbound attempts")


class InventoryHealthItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    local_id: str = Field(..., description="Location identifier (e.g. MED-001, MIA-001)")
    ingredient_id: str = Field(..., description="Ingredient UUID")
    ingredient_sku: str = Field(..., description="Ingredient SKU code (e.g. ING-001)")
    ingredient_name: str = Field(..., description="Ingredient display name")
    category: str = Field(..., description="Ingredient category")
    unit_of_measure: str = Field(..., description="Unit of measure (e.g. kg, l, und)")
    current_stock: float = Field(..., description="Authoritative stock level")
    minimum_stock: float = Field(..., description="Configured safety threshold")
    stock_level_ratio: Optional[float] = Field(default=None, description="Ratio current_stock / minimum_stock")
    stock_deficit: float = Field(..., description="Deficit relative to minimum stock (0 if healthy)")
    is_stockout: bool = Field(..., description="True if current_stock <= 0")
    is_below_minimum: bool = Field(..., description="True if current_stock <= minimum_stock")
    inbound_quantity: float = Field(default=0.0, description="Total inbound quantity")
    outbound_quantity: float = Field(default=0.0, description="Total outbound quantity")
    insufficient_stock_attempts_count: int = Field(default=0, description="Count of insufficient stock attempts")
    source_event_count: int = Field(default=0, description="Count of contributing events")
    computed_at: Optional[str] = Field(default=None, description="Timestamp when snapshot partition was calculated")


class InventoryHealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    period: InventoryHealthPeriod
    summary: InventoryHealthSummary
    items: list[InventoryHealthItem]
    pipeline_run_id: Optional[str] = Field(default=None, description="Latest pipeline run ID contributing to snapshot")
