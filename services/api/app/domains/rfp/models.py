"""SQLModel persistence models for RFP intake (Parte 1)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class RfpTicket(SQLModel, table=True):
    __tablename__ = "rfp_ticket"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    status: str = Field(default="analizando", index=True)  # analizando | analisis_completo | descartado
    created_at: datetime = Field(default_factory=_now, nullable=False)
    updated_at: datetime = Field(default_factory=_now, nullable=False)
    original_filename: str = Field(nullable=False)
    storage_path: str = Field(nullable=False)
    mime_type: str = Field(default="application/pdf", nullable=False)
    size_bytes: int = Field(default=0, nullable=False)
    submitted_by_uuid: Optional[uuid.UUID] = Field(default=None, index=True)
    error_code: Optional[str] = Field(default=None)
    error_detail: Optional[str] = Field(default=None)
    failed_at: Optional[datetime] = Field(default=None)
    retry_count: int = Field(default=0, nullable=False)
    processing_started_at: Optional[datetime] = Field(default=None)
    processing_completed_at: Optional[datetime] = Field(default=None)
    idempotency_key: str = Field(nullable=False, unique=True, index=True)


class RfpMetadata(SQLModel, table=True):
    __tablename__ = "rfp_metadata"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    extracted_at: datetime = Field(default_factory=_now, nullable=False)
    fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))


class RfpReadabilityMetrics(SQLModel, table=True):
    __tablename__ = "rfp_readability_metrics"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    metric_name: str = Field(nullable=False)
    value: float = Field(nullable=False)
    language: str = Field(default="unknown", nullable=False)
    limitations_note: str = Field(default="", nullable=False)
    calculated_at: datetime = Field(default_factory=_now, nullable=False)


class RfpClassification(SQLModel, table=True):
    __tablename__ = "rfp_classification"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    is_rfp: bool = Field(nullable=False)
    reason: str = Field(default="", nullable=False)
    confidence: float = Field(default=0.0, nullable=False)
    model: str = Field(default="", nullable=False)
    classified_at: datetime = Field(default_factory=_now, nullable=False)
    raw_output: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class RfpDepartmentAspect(SQLModel, table=True):
    __tablename__ = "rfp_department_aspect"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    department: str = Field(nullable=False, index=True)
    aspect: str = Field(nullable=False)
    detail: str = Field(default="", nullable=False)
    source_excerpt: str = Field(default="", nullable=False)
    created_at: datetime = Field(default_factory=_now, nullable=False)


class RfpDepartmentContact(SQLModel, table=True):
    __tablename__ = "rfp_department_contact"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    department: str = Field(nullable=False, index=True)
    name: str = Field(default="", nullable=False)
    role: str = Field(default="", nullable=False)
    email: str = Field(default="", nullable=False)
    phone: str = Field(default="", nullable=False)
    source_excerpt: str = Field(default="", nullable=False)
    created_at: datetime = Field(default_factory=_now, nullable=False)


class RfpSynthesis(SQLModel, table=True):
    __tablename__ = "rfp_synthesis"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    client_request_summary: str = Field(default="", nullable=False)
    intervening_departments: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    summary: str = Field(default="", nullable=False)
    created_at: datetime = Field(default_factory=_now, nullable=False)


class RfpHandoff(SQLModel, table=True):
    __tablename__ = "rfp_handoff"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    key_aspects: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    workstreams: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    prepared_at: datetime = Field(default_factory=_now, nullable=False)
    consumed_at: Optional[datetime] = Field(default=None)
    consumed_by: Optional[str] = Field(default=None)
