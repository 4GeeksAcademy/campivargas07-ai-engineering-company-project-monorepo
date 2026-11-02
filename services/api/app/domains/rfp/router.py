"""FastAPI router for RFP intake (Parte 1)."""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from app.database import get_db
from app.domains.auth.dependencies import get_current_user
from app.domains.rfp import events as rfp_events
from app.domains.rfp import service as rfp_service
from app.domains.rfp.errors import RfpNotFoundError
from app.domains.rfp.models import RfpTicket
from app.domains.rfp.repository import RfpRepository
from app.domains.rfp.schemas import (
    RfpCreateResponse,
    RfpGenerateResponse,
    RfpGenerationHandoffResponse,
    RfpGenerationRunResponse,
    RfpResultResponse,
    RfpSectionDraftResponse,
    RfpSectionEvaluationResponse,
    RfpStatusResponse,
)

router = APIRouter(prefix="/rfp-requests", tags=["rfp"])


@router.get("/events")
async def stream_rfp_events(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    last_event_id = request.headers.get("last-event-id") or request.query_params.get("last_event_id")
    return StreamingResponse(
        rfp_events.rfp_ticket_event_stream(request, current_user, last_event_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("")
def list_rfp_requests(
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    from sqlmodel import select

    from app.domains.rfp.models import RfpTicket

    stmt = select(RfpTicket).order_by(RfpTicket.created_at.desc()).limit(50)
    tickets = list(session.exec(stmt).all())
    return [
        {
            "ticket_id": str(t.id),
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
            "original_filename": t.original_filename,
        }
        for t in tickets
    ]


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


@router.post("/{ticket_id}/generate", status_code=202, response_model=RfpGenerateResponse)
def generate_rfp_request(
    ticket_id: uuid.UUID,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket, run = rfp_service.start_rfp_generation(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    background_tasks.add_task(rfp_service.process_rfp_generation, ticket.id)
    return RfpGenerateResponse(ticket_id=ticket.id, status=ticket.status, run_id=run.id)


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
    repo = RfpRepository(session)
    run = repo.get_generation_run(ticket_id)
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
        generation_status=run.status if run else None,
        current_iteration=run.current_iteration if run else None,
        all_sections_approved=run.all_sections_approved if run else None,
        needs_human_review=run.needs_human_review if run else None,
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
    generation_run = repo.get_generation_run(ticket_id)
    drafts = repo.list_drafts(ticket_id)
    evaluations = repo.list_evaluations(ticket_id)
    generation_handoff = repo.get_generation_handoff(ticket_id)

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
        generation_run=RfpGenerationRunResponse(
            id=generation_run.id,
            status=generation_run.status,
            active_departments=generation_run.active_departments,
            max_iterations=generation_run.max_iterations,
            current_iteration=generation_run.current_iteration,
            all_sections_approved=generation_run.all_sections_approved,
            needs_human_review=generation_run.needs_human_review,
            needs_human_review_reason=generation_run.needs_human_review_reason,
            error_code=generation_run.error_code,
            error_detail=generation_run.error_detail,
            global_compliance=generation_run.global_compliance,
            completed_at=generation_run.completed_at,
        )
        if generation_run
        else None,
        drafts=[
            RfpSectionDraftResponse(
                id=d.id,
                department_id=d.department_id,
                version=d.version,
                iteration=d.iteration,
                content=d.content,
                generator_id=d.generator_id,
                model=d.model,
                status=d.status,
                created_at=d.created_at,
            )
            for d in drafts
        ],
        evaluations=[
            RfpSectionEvaluationResponse(
                id=e.id,
                department_id=e.department_id,
                draft_id=e.draft_id,
                iteration=e.iteration,
                readability=e.readability,
                relevance=e.relevance,
                compliance=e.compliance,
                overall_pass=e.overall_pass,
                feedback_for_generator=e.feedback_for_generator,
                evaluated_at=e.evaluated_at,
            )
            for e in evaluations
        ],
        generation_handoff=RfpGenerationHandoffResponse(
            ticket_id=generation_handoff.ticket_id,
            sections=generation_handoff.sections,
            global_compliance=generation_handoff.global_compliance,
            open_questions=generation_handoff.open_questions,
            requires_ceo_approval=generation_handoff.requires_ceo_approval,
            prepared_at=generation_handoff.prepared_at,
        )
        if generation_handoff
        else None,
    )
