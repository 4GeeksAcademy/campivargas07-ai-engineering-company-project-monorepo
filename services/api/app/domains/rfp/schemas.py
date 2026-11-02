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
