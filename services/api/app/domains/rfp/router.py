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
from app.domains.rfp.errors import RfpNotFoundError, RfpValidationError
from app.domains.rfp.models import RfpTicket
from app.domains.rfp.repository import RfpRepository
from app.domains.rfp.schemas import (
    RfpApprovalDecisionRequest,
    RfpApproverAssignRequest,
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


@router.post("/{ticket_id}/approval/start", status_code=202)
def start_approval(
    ticket_id: uuid.UUID,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket, run = rfp_service.start_rfp_approval(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    background_tasks.add_task(rfp_service.process_rfp_approval, ticket.id)
    return {"ticket_id": str(ticket.id), "status": ticket.status, "run_id": str(run.id)}


@router.get("/{ticket_id}/approvals")
def get_approvals(
    ticket_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket = rfp_service.get_ticket(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    repo = RfpRepository(session)
    run = repo.get_approval_run(ticket_id)
    approvals = repo.list_human_approvals(ticket_id)
    conflicts = repo.list_conflicts(ticket_id)
    final_doc = repo.get_final_document(ticket_id)
    return {
        "ticket_id": str(ticket.id),
        "status": ticket.status,
        "approvals": [a.__dict__ for a in approvals],
        "conflicts": [c.__dict__ for c in conflicts],
        "requires_ceo_approval": run.requires_ceo_approval if run else False,
        "ceo_approved": run.ceo_approved if run else False,
        "correction_cycle": run.correction_cycle if run else 0,
        "final_document_id": str(run.final_document_id) if (run and run.final_document_id) else None,
        "final_document_reference": final_doc.file_reference if final_doc else None,
    }


@router.get("/{ticket_id}/approvals/{department_id}")
def get_department_review(
    ticket_id: uuid.UUID,
    department_id: str,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket = rfp_service.get_ticket(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    repo = RfpRepository(session)
    gen_handoff = repo.get_generation_handoff(ticket_id)
    section = None
    if gen_handoff is not None:
        for s in (gen_handoff.sections or []):
            if isinstance(s, dict) and s.get("department_id") == department_id:
                section = s
                break
    drafts = [d for d in repo.list_drafts(ticket_id) if d.department_id == department_id]
    latest_draft = max(drafts, key=lambda x: x.version) if drafts else None
    evals = [e for e in repo.list_evaluations(ticket_id) if e.department_id == department_id]
    latest_eval = max(evals, key=lambda x: x.iteration) if evals else None
    return {
        "ticket_id": str(ticket.id),
        "department_id": department_id,
        "section": section,
        "draft": {
            "id": str(latest_draft.id) if latest_draft else None,
            "version": latest_draft.version if latest_draft else None,
            "content": latest_draft.content if latest_draft else None,
        },
        "evaluation": {
            "overall_pass": latest_eval.overall_pass if latest_eval else None,
            "readability": latest_eval.readability if latest_eval else None,
            "relevance": latest_eval.relevance if latest_eval else None,
            "compliance": latest_eval.compliance if latest_eval else None,
            "feedback_for_generator": latest_eval.feedback_for_generator if latest_eval else None,
        } if latest_eval else None,
        "global_compliance": gen_handoff.global_compliance if gen_handoff else None,
        "open_questions": gen_handoff.open_questions if gen_handoff else [],
        "requires_ceo_approval": gen_handoff.requires_ceo_approval if gen_handoff else False,
    }


@router.post("/{ticket_id}/approvals/{department_id}")
def submit_department_decision(
    ticket_id: uuid.UUID,
    department_id: str,
    payload: RfpApprovalDecisionRequest,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = rfp_service.submit_approval_decision(
            session=session,
            ticket_id=ticket_id,
            department_id=department_id,
            decision=payload.decision,
            comment=payload.comment,
            version=payload.version,
            current_user=current_user,
        )
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    except RfpValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.post("/{ticket_id}/approvals/ceo")
def submit_ceo_decision(
    ticket_id: uuid.UUID,
    payload: RfpApprovalDecisionRequest,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        result = rfp_service.submit_approval_decision(
            session=session,
            ticket_id=ticket_id,
            department_id="ceo",
            decision=payload.decision,
            comment=payload.comment,
            version=None,
            current_user=current_user,
        )
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    except RfpValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return result


@router.get("/{ticket_id}/final-document")
def get_final_document(
    ticket_id: uuid.UUID,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        ticket = rfp_service.get_ticket(session, ticket_id)
    except RfpNotFoundError:
        raise HTTPException(status_code=404, detail="RFP ticket not found.")
    repo = RfpRepository(session)
    doc = repo.get_final_document(ticket_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Final document not found.")
    return {
        "ticket_id": str(ticket.id),
        "id": str(doc.id),
        "content": doc.content,
        "file_reference": doc.file_reference,
        "sections": doc.sections,
        "total_estimated_value": doc.total_estimated_value,
        "generated_at": doc.generated_at,
    }


@router.post("/approvers", status_code=201)
def assign_approver(
    payload: RfpApproverAssignRequest,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        row = rfp_service.assign_department_approver(
            session=session,
            department_id=payload.department_id,
            user_uuid=payload.user_uuid,
            responsible_name=payload.responsible_name,
            current_user=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    return {"department_id": row.department_id, "user_uuid": row.user_uuid, "responsible_name": row.responsible_name}


@router.get("/approvers/{department_id}")
def list_approvers(
    department_id: str,
    session: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    rows = rfp_service.list_department_approvers(session, department_id)
    return [{"department_id": r.department_id, "user_uuid": r.user_uuid, "responsible_name": r.responsible_name} for r in rows]
