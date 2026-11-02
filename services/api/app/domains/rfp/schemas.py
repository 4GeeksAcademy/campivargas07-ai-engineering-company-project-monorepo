"""Pydantic schemas for RFP intake API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RfpCreateResponse(BaseModel):
    ticket_id: UUID
    status: str


class RfpStatusResponse(BaseModel):
    ticket_id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    original_filename: str
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    retry_count: int = 0
    generation_status: Optional[str] = None
    current_iteration: Optional[int] = None
    all_sections_approved: Optional[bool] = None
    needs_human_review: Optional[bool] = None


class RfpMetadataResponse(BaseModel):
    ticket_id: UUID
    fields: dict[str, Any]
    extracted_at: datetime


class RfpReadabilityResponse(BaseModel):
    metric_name: str
    value: float
    language: str
    limitations_note: str


class RfpClassificationResponse(BaseModel):
    is_rfp: bool
    reason: str
    confidence: float


class RfpDepartmentAspectResponse(BaseModel):
    department: str
    aspect: str
    detail: str
    source_excerpt: str


class RfpDepartmentContactResponse(BaseModel):
    department: str
    name: str
    role: str
    email: str
    phone: str
    source_excerpt: str


class RfpSynthesisResponse(BaseModel):
    client_request_summary: str
    intervening_departments: list[str]
    summary: str


class RfpHandoffResponse(BaseModel):
    ticket_id: UUID
    key_aspects: list[dict[str, Any]]
    workstreams: list[dict[str, Any]]
    prepared_at: datetime


class RfpSectionDraftResponse(BaseModel):
    id: UUID
    department_id: str
    version: int
    iteration: int
    content: str
    generator_id: str
    model: str
    status: str
    created_at: datetime


class RfpSectionEvaluationResponse(BaseModel):
    id: UUID
    department_id: str
    draft_id: Optional[UUID] = None
    iteration: int
    readability: dict[str, Any]
    relevance: dict[str, Any]
    compliance: dict[str, Any]
    overall_pass: bool
    feedback_for_generator: str
    evaluated_at: datetime


class RfpGenerationRunResponse(BaseModel):
    id: UUID
    status: str
    active_departments: list[str]
    max_iterations: int
    current_iteration: int
    all_sections_approved: bool
    needs_human_review: bool
    needs_human_review_reason: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    global_compliance: Optional[dict[str, Any]] = None
    completed_at: Optional[datetime] = None


class RfpGenerationHandoffResponse(BaseModel):
    ticket_id: UUID
    sections: list[dict[str, Any]]
    global_compliance: Optional[dict[str, Any]] = None
    open_questions: list[str] = Field(default_factory=list)
    requires_ceo_approval: Optional[bool] = None
    prepared_at: datetime


class RfpGenerateResponse(BaseModel):
    ticket_id: UUID
    status: str
    run_id: UUID


class RfpResultResponse(BaseModel):
    ticket_id: UUID
    status: str
    metadata: Optional[RfpMetadataResponse] = None
    readability: list[RfpReadabilityResponse] = Field(default_factory=list)
    classification: Optional[RfpClassificationResponse] = None
    aspects: list[RfpDepartmentAspectResponse] = Field(default_factory=list)
    contacts: list[RfpDepartmentContactResponse] = Field(default_factory=list)
    synthesis: Optional[RfpSynthesisResponse] = None
    handoff: Optional[RfpHandoffResponse] = None
    generation_run: Optional[RfpGenerationRunResponse] = None
    drafts: list[RfpSectionDraftResponse] = Field(default_factory=list)
    evaluations: list[RfpSectionEvaluationResponse] = Field(default_factory=list)
    generation_handoff: Optional[RfpGenerationHandoffResponse] = None


class RfpApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., description="approve | reject | request_changes")
    comment: str = Field(default="", description="Obligatorio para reject/request_changes")
    version: Optional[int] = Field(default=None, description="Versión exacta del borrador")


class RfpApprovalResponse(BaseModel):
    ticket_id: UUID
    department_id: str
    decision: str
    version: Optional[int] = None
    status: str


class RfpApprovalSummaryResponse(BaseModel):
    ticket_id: UUID
    status: str
    approvals: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    requires_ceo_approval: bool = False
    ceo_approved: bool = False
    correction_cycle: int = 0
    final_document_id: Optional[UUID] = None
    final_document_reference: Optional[str] = None


class RfpFinalDocumentResponse(BaseModel):
    ticket_id: UUID
    id: UUID
    content: str
    file_reference: str
    sections: list[dict[str, Any]] = Field(default_factory=list)
    total_estimated_value: Optional[float] = None
    generated_at: datetime
