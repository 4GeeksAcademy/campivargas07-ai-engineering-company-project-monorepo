"""
models.py — Brasaland · SQLModel definitions for the `reporting` schema.

Reflects tables created in migration 002_create_inventory_health_reporting.sql:
- InventoryHealthSnapshotRecord
- PipelineCheckpointRecord
- InventoryHealthLineageRecord
- InventoryHealthQuarantineRecord
- PipelineExecutionLogRecord
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class InventoryHealthSnapshotRecord(SQLModel, table=True):
    __tablename__ = "inventory_health_snapshot"
    __table_args__ = {"schema": "reporting"}

    snapshot_date: date = Field(primary_key=True)
    local_id: str = Field(max_length=50, primary_key=True)
    ingredient_id: UUID = Field(primary_key=True)
    ingredient_sku: str = Field(max_length=50)
    ingredient_name: str = Field(max_length=150)
    category: str = Field(max_length=50)
    unit_of_measure: str = Field(max_length=30)
    current_stock: float
    minimum_stock: float
    stock_level_ratio: Optional[float] = Field(default=None)
    stock_deficit: float
    is_stockout: bool
    is_below_minimum: bool
    inbound_quantity: float = Field(default=0.0)
    outbound_quantity: float = Field(default=0.0)
    insufficient_stock_attempts_count: int = Field(default=0)
    source_event_count: int = Field(default=0)
    source_first_event_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    source_last_event_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    pipeline_run_id: UUID
    computed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class PipelineCheckpointRecord(SQLModel, table=True):
    __tablename__ = "pipeline_checkpoints"
    __table_args__ = {"schema": "reporting"}

    pipeline_name: str = Field(max_length=100, primary_key=True)
    source_name: str = Field(max_length=100, primary_key=True)
    watermark_timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    watermark_event_id: UUID
    last_successful_run_id: UUID
    updated_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class InventoryHealthLineageRecord(SQLModel, table=True):
    __tablename__ = "inventory_health_lineage"
    __table_args__ = {"schema": "reporting"}

    pipeline_run_id: UUID = Field(primary_key=True)
    event_id: UUID = Field(primary_key=True)
    snapshot_date: date
    local_id: str = Field(max_length=50)
    ingredient_id: UUID
    processed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class InventoryHealthQuarantineRecord(SQLModel, table=True):
    __tablename__ = "inventory_health_quarantine"
    __table_args__ = {"schema": "reporting"}

    quarantine_id: UUID = Field(primary_key=True)
    event_id: Optional[UUID] = Field(default=None)
    pipeline_run_id: UUID
    event_type: str = Field(max_length=100)
    reason_code: str = Field(max_length=50)
    reason_detail: str
    raw_payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            JSON().with_variant(JSONB, "postgresql"),
            nullable=False,
            server_default=text("'{}'"),
        ),
    )
    quarantined_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class PipelineExecutionLogRecord(SQLModel, table=True):
    __tablename__ = "pipeline_execution_logs"
    __table_args__ = {"schema": "reporting"}

    pipeline_run_id: UUID = Field(primary_key=True)
    started_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    pipeline_run_status: str = Field(max_length=30)
    watermark_timestamp: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    source_events_read: int = Field(default=0)
    records_quarantined: int = Field(default=0)
    error_detail: Optional[str] = Field(default=None)
