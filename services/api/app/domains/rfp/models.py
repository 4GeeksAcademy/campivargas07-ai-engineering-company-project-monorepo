"""SQLModel persistence models for RFP intake (Parte 1)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, JSON, UniqueConstraint
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


class RfpGenerationRun(SQLModel, table=True):
    __tablename__ = "rfp_generation_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    status: str = Field(default="pendiente", index=True)  # pendiente | running | completed | failed
    active_departments: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    max_iterations: int = Field(default=3, nullable=False)
    current_iteration: int = Field(default=0, nullable=False)
    all_sections_approved: bool = Field(default=False, nullable=False)
    needs_human_review: bool = Field(default=False, nullable=False)
    needs_human_review_reason: Optional[str] = Field(default=None)
    error_code: Optional[str] = Field(default=None)
    error_detail: Optional[str] = Field(default=None)
    global_compliance: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=_now, nullable=False)
    updated_at: datetime = Field(default_factory=_now, nullable=False)
    completed_at: Optional[datetime] = Field(default=None)


class RfpSectionDraft(SQLModel, table=True):
    __tablename__ = "rfp_section_draft"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    department_id: str = Field(nullable=False, index=True)
    version: int = Field(nullable=False)
    iteration: int = Field(nullable=False)
    content: str = Field(nullable=False)
    generator_id: str = Field(default="", nullable=False)
    model: str = Field(default="", nullable=False)
    prompt_hash: Optional[str] = Field(default=None)
    status: str = Field(default="draft", nullable=False)
    created_at: datetime = Field(default_factory=_now, nullable=False)


class RfpSectionEvaluation(SQLModel, table=True):
    __tablename__ = "rfp_section_evaluation"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    department_id: str = Field(nullable=False, index=True)
    draft_id: Optional[uuid.UUID] = Field(default=None, foreign_key="rfp_section_draft.id")
    iteration: int = Field(nullable=False)
    readability: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    relevance: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    compliance: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    overall_pass: bool = Field(default=False, nullable=False)
    feedback_for_generator: str = Field(default="", nullable=False)
    evaluated_at: datetime = Field(default_factory=_now, nullable=False)


class RfpGenerationHandoff(SQLModel, table=True):
    __tablename__ = "rfp_generation_handoff"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    sections: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    global_compliance: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    open_questions: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    requires_ceo_approval: Optional[bool] = Field(default=None)
    prepared_at: datetime = Field(default_factory=_now, nullable=False)
    consumed_at: Optional[datetime] = Field(default=None)
    consumed_by: Optional[str] = Field(default=None)

class RfpTicketEvent(SQLModel, table=True):
    """Durable SSE event log for RFP ticket arrivals (Parte 1 de 2)."""

    __tablename__ = "rfp_ticket_event"
    __table_args__ = (UniqueConstraint("ticket_id", "event_type", name="uq_rfp_ticket_event_ticket_type"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    event_type: str = Field(default="rfp_ticket_created", nullable=False, index=True)
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    submitted_by_uuid: Optional[uuid.UUID] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_now, nullable=False)



class RfpApprovalRun(SQLModel, table=True):
    __tablename__ = "rfp_approval_run"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    thread_id: str = Field(nullable=False)
    status: str = Field(default="pendiente", index=True)  # pendiente | running | esperando_aprobación | completado | failed | agotado | rechazado
    active_departments: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    requires_ceo_approval: bool = Field(default=False, nullable=False)
    ceo_approved: bool = Field(default=False, nullable=False)
    correction_cycle: int = Field(default=0, nullable=False)
    max_correction_cycles: int = Field(default=3, nullable=False)
    conflicts: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    sections_to_correct: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    final_document_id: Optional[uuid.UUID] = Field(default=None, foreign_key="rfp_final_document.id")
    error_code: Optional[str] = Field(default=None)
    error_detail: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=_now, nullable=False)
    updated_at: datetime = Field(default_factory=_now, nullable=False)
    completed_at: Optional[datetime] = Field(default=None)


class RfpHumanApproval(SQLModel, table=True):
    __tablename__ = "rfp_human_approval"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    department_id: str = Field(nullable=False, index=True)
    draft_id: Optional[uuid.UUID] = Field(default=None, foreign_key="rfp_section_draft.id")
    version: int = Field(nullable=False)
    decision: str = Field(nullable=False)  # approve | reject | request_changes
    comment: str = Field(default="", nullable=False)
    approver_uuid: str = Field(nullable=False, index=True)
    interrupt_id: Optional[str] = Field(default=None)
    resumed_at: Optional[datetime] = Field(default=None)
    decided_at: datetime = Field(default_factory=_now, nullable=False)


class RfpConflict(SQLModel, table=True):
    __tablename__ = "rfp_conflict"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False)
    trigger_id: str = Field(nullable=False, index=True)
    departments: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    summary: str = Field(default="", nullable=False)
    arbiter: str = Field(default="", nullable=False)
    status: str = Field(default="open", index=True)  # open | resolved
    resolution: str = Field(default="", nullable=False)
    created_at: datetime = Field(default_factory=_now, nullable=False)
    resolved_at: Optional[datetime] = Field(default=None)


class RfpFinalDocument(SQLModel, table=True):
    __tablename__ = "rfp_final_document"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    ticket_id: uuid.UUID = Field(foreign_key="rfp_ticket.id", index=True, nullable=False, unique=True)
    content: str = Field(nullable=False)
    file_reference: str = Field(default="", nullable=False)
    sections: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    total_estimated_value: Optional[float] = Field(default=None)
    generated_at: datetime = Field(default_factory=_now, nullable=False)


class RfpDepartmentApprover(SQLModel, table=True):
    __tablename__ = "rfp_department_approver"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    department_id: str = Field(nullable=False, index=True)
    user_uuid: str = Field(nullable=False, index=True)
    responsible_name: str = Field(default="", nullable=False)
    created_at: datetime = Field(default_factory=_now, nullable=False)
