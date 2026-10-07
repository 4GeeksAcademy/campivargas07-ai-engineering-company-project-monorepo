"""
models.py — Brasaland · Telemetry domain ORM models (SQLModel / PostgreSQL)

Represents the append-only event store for telemetry events:
- Exactly eight columns: event_id, event_type, timestamp, service, session_id, user_id, request_id, tags.
- Three explicit indexes: timestamp, event_type, tags (GIN).
- Immutable, append-only log.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Column, DateTime, Index, JSON, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class TelemetryEventRecord(SQLModel, table=True):
    """
    Append-only telemetry events record.
    Persists exactly eight columns with zero update/delete capabilities.
    """

    __tablename__ = "telemetry_events"
    __table_args__ = (
        Index("idx_telemetry_events_timestamp", "timestamp"),
        Index("idx_telemetry_events_event_type", "event_type"),
        Index("idx_telemetry_events_tags_gin", "tags", postgresql_using="gin"),
    )

    event_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(
            Uuid,
            primary_key=True,
            nullable=False,
        ),
        description="Immutable unique event identifier (UUID v4) for idempotency",
    )
    event_type: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Canonical event name according to taxonomy",
    )
    timestamp: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False),
        description="UTC event occurrence timestamp with timezone",
    )
    service: str = Field(
        default="backoffice",
        sa_column=Column(String(50), nullable=False),
        description="Producer service identifier assigned by the server",
    )
    session_id: Optional[str] = Field(
        default=None,
        sa_column=Column(String(100), nullable=True),
        description="Ephemeral web session identifier",
    )
    user_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            Uuid,
            nullable=True,
        ),
        description="Pseudonymized user UUID",
    )
    request_id: str = Field(
        sa_column=Column(String(100), nullable=False),
        description="Correlation / trace request identifier",
    )
    tags: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"), nullable=False),
        description="JSONB document containing only validated properties",
    )

