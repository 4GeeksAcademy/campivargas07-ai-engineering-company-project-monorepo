"""FastAPI router for RFP intake (Parte 1)."""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlmodel import Session

from app.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.rfp import service as rfp_service
from app.domains.rfp.errors import RfpNotFoundError
from app.domains.rfp.models import RfpTicket
from app.domains.rfp.repository import RfpRepository
from app.domains.rfp.schemas import (
    RfpCreateResponse,
    RfpResultResponse,
    RfpStatusResponse,
)

router = APIRouter(prefix="/rfp-requests", tags=["rfp"])


def _current_user_uuid(current_user: dict) -> Optional[uuid.UUID]:
    raw = current_user.get("uuid")
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


@router.post("", status_code=202, response_model=RfpCreateResponse)
async def create_rfp_request(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_db),
):
    if file.content_type not in ("application/pdf", "application/octet-stream") and not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file.")

    idempotency_key = hashlib.sha256(content).hexdigest() + ":" + str(_current_user_uuid(current_user))

    ticket = rfp_service.create_ticket(
        session=session,
        filename=file.filename or "upload.pdf",
        content=content,
        submitted_by_uuid=_current_user_uuid(current_user),
        idempotency_key=idempotency_key,
    )

    background_tasks.add_task(rfp_service.process_rfp_ticket, ticket.id)

    return RfpCreateResponse(ticket_id=ticket.id, status=ticket.status)


@router.get("/{ticket_id}", response_model=RfpStatusResponse)
def get_rfp_status(
    ticket_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket = rfp_service.get_ticket(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    return RfpStatusResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        original_filename=ticket.original_filename,
        error_code=ticket.error_code,
        error_detail=ticket.error_detail,
        processing_started_at=ticket.processing_started_at,
        processing_completed_at=ticket.processing_completed_at,
        retry_count=ticket.retry_count,
    )


@router.get("/{ticket_id}/result", response_model=RfpResultResponse)
def get_rfp_result(
    ticket_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket = rfp_service.get_ticket(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")

    repo = RfpRepository(session)
    metadata = repo.get_metadata(ticket_id)
    readability = repo.list_readability(ticket_id)
    classification = repo.get_classification(ticket_id)
    aspects = repo.list_aspects(ticket_id)
    contacts = repo.list_contacts(ticket_id)
    synthesis = repo.get_synthesis(ticket_id)
    handoff = repo.get_handoff(ticket_id)

    from app.domains.rfp.schemas import (
        RfpClassificationResponse,
        RfpDepartmentAspectResponse,
        RfpDepartmentContactResponse,
        RfpHandoffResponse,
        RfpMetadataResponse,
        RfpReadabilityResponse,
        RfpSynthesisResponse,
    )

    return RfpResultResponse(
        ticket_id=ticket.id,
        status=ticket.status,
        metadata=RfpMetadataResponse(ticket_id=ticket.id, fields=metadata.fields, extracted_at=metadata.extracted_at) if metadata else None,
        readability=[
            RfpReadabilityResponse(
                metric_name=m.metric_name,
                value=m.value,
                language=m.language,
                limitations_note=m.limitations_note,
            )
            for m in readability
        ],
        classification=RfpClassificationResponse(
            is_rfp=classification.is_rfp,
            reason=classification.reason,
            confidence=classification.confidence,
        )
        if classification
        else None,
        aspects=[
            RfpDepartmentAspectResponse(
                department=a.department,
                aspect=a.aspect,
                detail=a.detail,
                source_excerpt=a.source_excerpt,
            )
            for a in aspects
        ],
        contacts=[
            RfpDepartmentContactResponse(
                department=c.department,
                name=c.name,
                role=c.role,
                email=c.email,
                phone=c.phone,
                source_excerpt=c.source_excerpt,
            )
            for c in contacts
        ],
        synthesis=RfpSynthesisResponse(
            client_request_summary=synthesis.client_request_summary,
            intervening_departments=synthesis.intervening_departments,
            summary=synthesis.summary,
        )
        if synthesis
        else None,
        handoff=RfpHandoffResponse(
            ticket_id=handoff.ticket_id,
            key_aspects=handoff.key_aspects,
            workstreams=handoff.workstreams,
            prepared_at=handoff.prepared_at,
        )
        if handoff
        else None,
    )
