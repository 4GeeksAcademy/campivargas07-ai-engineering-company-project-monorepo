"""RFP intake service: ticket lifecycle, async processing, persistence."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlmodel import Session

from app.database import get_db_engine
from app.domains.rfp.errors import RfpNotFoundError
from app.domains.rfp.models import (
    RfpClassification,
    RfpDepartmentAspect,
    RfpDepartmentContact,
    RfpHandoff,
    RfpMetadata,
    RfpReadabilityMetrics,
    RfpSynthesis,
    RfpTicket,
)
from app.domains.rfp.repository import RfpRepository

RAW_DIR = Path(os.environ.get("RFP_RAW_DIR", str(Path(__file__).resolve().parents[5] / "data" / "raw")))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def raw_path_for(ticket_id: uuid.UUID, filename: str) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    safe = filename.replace("/", "_").replace("\\", "_")
    return RAW_DIR / f"{ticket_id}__{safe}"


def create_ticket(
    *,
    session: Session,
    filename: str,
    content: bytes,
    submitted_by_uuid: Optional[uuid.UUID],
    idempotency_key: str,
) -> RfpTicket:
    repo = RfpRepository(session)
    existing = repo.get_ticket_by_idempotency(idempotency_key)
    if existing is not None:
        return existing

    ticket_id = uuid.uuid4()
    storage_path = raw_path_for(ticket_id, filename)
    storage_path.write_bytes(content)

    ticket = RfpTicket(
        id=ticket_id,
        status="analizando",
        original_filename=filename,
        storage_path=str(storage_path),
        mime_type="application/pdf",
        size_bytes=len(content),
        submitted_by_uuid=submitted_by_uuid,
        idempotency_key=idempotency_key,
    )
    return repo.create_ticket(ticket)


def get_ticket(session: Session, ticket_id: uuid.UUID) -> RfpTicket:
    repo = RfpRepository(session)
    ticket = repo.get_ticket(ticket_id)
    if ticket is None:
        raise RfpNotFoundError(f"RFP ticket {ticket_id} not found.")
    return ticket


def process_rfp_ticket(ticket_id: uuid.UUID) -> None:
    """Background job: runs the full intake pipeline for a ticket."""
    try:
        engine = get_db_engine()
    except RuntimeError:
        return
    with Session(engine) as session:
        repo = RfpRepository(session)
        ticket = repo.get_ticket(ticket_id)
        if ticket is None:
            return
        if ticket.status not in ("analizando",):
            return

        ticket.processing_started_at = _now()
        ticket.retry_count = (ticket.retry_count or 0) + 1
        ticket.error_code = None
        ticket.error_detail = None
        ticket.failed_at = None
        repo.update_ticket(ticket)

        try:
            import sys

            repo_root = Path(__file__).resolve().parents[5]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            from data.pipelines.rfp_intake import run_rfp_intake

            language = _detect_language("")
            # Read file bytes to detect language from first pages is not needed; keep unknown.
            result = run_rfp_intake(str(ticket.id), ticket.storage_path, language="unknown")

            metadata_fields = result.get("metadata", {}) or {}
            repo.save_metadata(RfpMetadata(ticket_id=ticket.id, fields=metadata_fields))

            for metric in result.get("readability", []) or []:
                repo.save_readability(
                    RfpReadabilityMetrics(
                        ticket_id=ticket.id,
                        metric_name=metric["metric_name"],
                        value=metric["value"],
                        language=metric["language"],
                        limitations_note=metric["limitations_note"],
                    )
                )

            classification_result = result.get("classification")
            if classification_result is not None:
                repo.save_classification(
                    RfpClassification(
                        ticket_id=ticket.id,
                        is_rfp=bool(classification_result.get("is_rfp", False)),
                        reason=str(classification_result.get("reason", "")),
                        confidence=float(classification_result.get("confidence", 0.0)),
                        model=str(classification_result.get("model", "")),
                        raw_output=classification_result,
                    )
                )

                # SSE notification (Parte 1): solo RFPs válidas, después de persistir
                # metadata+clasificación y antes del trabajo posterior.
                if bool(classification_result.get("is_rfp", False)):
                    payload = {
                        "ticket_id": str(ticket.id),
                        "client_name": str(metadata_fields.get("client_name", "")),
                        "location": str(metadata_fields.get("location", "")),
                        "service_type": str(metadata_fields.get("service_type", "")),
                        "status": "analyzing",
                        "created_at": ticket.created_at.isoformat(),
                        "departments_needed": list(metadata_fields.get("departments_needed", []) or []),
                    }
                    repo.record_ticket_event(
                        ticket_id=ticket.id,
                        event_type="rfp_ticket_created",
                        payload=payload,
                        submitted_by_uuid=ticket.submitted_by_uuid,
                    )

            outcome = result.get("outcome")
            if outcome == "descartado":
                ticket.status = "descartado"
                ticket.processing_completed_at = _now()
                repo.update_ticket(ticket)
                return

            if outcome == "analisis_completo":
                for dr in result.get("department_results", []) or []:
                    dept = dr.get("department", "")
                    for aspect in dr.get("aspects", []) or []:
                        repo.add_aspect(
                            RfpDepartmentAspect(
                                ticket_id=ticket.id,
                                department=dept,
                                aspect=str(aspect.get("aspect", "")),
                                detail=str(aspect.get("detail", "")),
                                source_excerpt=str(aspect.get("source_excerpt", "")),
                            )
                        )
                    for contact in dr.get("contacts", []) or []:
                        repo.add_contact(
                            RfpDepartmentContact(
                                ticket_id=ticket.id,
                                department=dept,
                                name=str(contact.get("name", "")),
                                role=str(contact.get("role", "")),
                                email=str(contact.get("email", "")),
                                phone=str(contact.get("phone", "")),
                                source_excerpt=str(contact.get("source_excerpt", "")),
                            )
                        )

                synthesis_result = result.get("synthesis", {}) or {}
                repo.save_synthesis(
                    RfpSynthesis(
                        ticket_id=ticket.id,
                        client_request_summary=str(synthesis_result.get("client_request_summary", "")),
                        intervening_departments=list(synthesis_result.get("intervening_departments", [])),
                        summary=str(synthesis_result.get("summary", "")),
                    )
                )
                handoff_payload = result.get("handoff", {}) or {}
                repo.save_handoff(
                    RfpHandoff(
                        ticket_id=ticket.id,
                        key_aspects=list(handoff_payload.get("key_aspects", [])),
                        workstreams=list(handoff_payload.get("workstreams", [])),
                    )
                )

                ticket.status = "analisis_completo"
                ticket.processing_completed_at = _now()
                repo.update_ticket(ticket)
                return

            # If graph did not reach a terminal business state (e.g. blocked), record technical failure.
            ticket.error_code = "blocked_pending_briefing"
            ticket.error_detail = "Pipeline did not reach a terminal business state (likely blocked pending official BRIEFING)."
            ticket.failed_at = _now()
            repo.update_ticket(ticket)

        except Exception as exc:  # noqa: BLE001
            from data.process.rfp import RfpBlockedError

            if isinstance(exc, RfpBlockedError):
                ticket.error_code = "blocked_pending_briefing"
            else:
                ticket.error_code = "processing_failed"
            ticket.error_detail = str(exc)[:1000]
            ticket.failed_at = _now()
            repo.update_ticket(ticket)


def _detect_language(markdown: str) -> str:
    # Heuristic: if common Spanish words present, assume es; else unknown.
    lowered = markdown.lower()
    spanish_markers = (" el ", " la ", " los ", " las ", " de ", " que ", " para ")
    hits = sum(1 for m in spanish_markers if m in f" {lowered} ")
    return "es" if hits >= 3 else "unknown"


def start_rfp_generation(session, ticket_id):
    import uuid as _uuid
    from app.domains.rfp.models import RfpGenerationRun

    ticket = get_ticket(session, ticket_id)
    if ticket.status not in ("analisis_completo", "generando_borrador", "en_evaluación", "needs_human_review"):
        raise ValueError(f"Ticket not ready for generation (status={ticket.status}).")

    repo = RfpRepository(session)
    run = repo.get_generation_run(ticket.id)
    if run is None:
        handoff = repo.get_handoff(ticket.id)
        if handoff is None:
            raise ValueError("Missing Parte 1 handoff.")
        active = []
        for ws in (handoff.workstreams or []):
            dept = ws.get("department") if isinstance(ws, dict) else None
            if dept:
                active.append(str(dept))
        if not active:
            raise ValueError("Handoff has no active departments.")
        handoff.consumed_at = _now()
        handoff.consumed_by = "rfp-response-generation"
        repo.update_handoff(handoff)

        run = RfpGenerationRun(
            ticket_id=ticket.id,
            status="pendiente",
            active_departments=active,
            max_iterations=3,
        )
        run = repo.create_generation_run(run)

    if ticket.status == "analisis_completo":
        ticket.status = "generando_borrador"
        ticket.updated_at = _now()
        repo.update_ticket(ticket)

    return ticket, run


def _group_aspects(session, ticket_id):
    repo = RfpRepository(session)
    aspects = repo.list_aspects(ticket_id)
    grouped = {}
    for a in aspects:
        grouped.setdefault(a.department, []).append(
            {"aspect": a.aspect, "detail": a.detail, "source_excerpt": a.source_excerpt}
        )
    return grouped


def process_rfp_generation(ticket_id):
    try:
        engine = get_db_engine()
    except RuntimeError:
        return
    with Session(engine) as session:
        repo = RfpRepository(session)
        ticket = repo.get_ticket(ticket_id)
        if ticket is None:
            return
        run = repo.get_generation_run(ticket.id)
        if run is None:
            return
        if run.status in ("completed", "failed"):
            return

        run.status = "running"
        run.error_code = None
        run.error_detail = None
        repo.update_generation_run(run)

        if ticket.status not in ("generando_borrador", "en_evaluación", "needs_human_review"):
            ticket.status = "generando_borrador"
        ticket.processing_started_at = ticket.processing_started_at or _now()
        repo.update_ticket(ticket)

        try:
            import sys
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[5]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            from data.pipelines.rfp_response_generation import run_rfp_response_generation
            from data.process.rfp_generation import load_settings

            metadata = {}
            meta = repo.get_metadata(ticket.id)
            if meta is not None:
                metadata = meta.fields or {}

            handoff = repo.get_handoff(ticket.id)
            active = run.active_departments or []
            if not active and handoff is not None:
                active = [ws.get("department") for ws in (handoff.workstreams or []) if isinstance(ws, dict)]
            active = [str(d) for d in active if d]

            aspects_by_department = _group_aspects(session, ticket.id)

            settings = load_settings()
            result = run_rfp_response_generation(
                ticket_id=str(ticket.id),
                active_departments=active,
                metadata=metadata,
                aspects_by_department=aspects_by_department,
                max_iterations=run.max_iterations,
                settings=settings,
            )

            if result.get("error_code"):
                run.status = "failed"
                run.error_code = result.get("error_code")
                run.error_detail = result.get("error_detail")
                ticket.error_code = run.error_code
                ticket.error_detail = run.error_detail
                ticket.failed_at = _now()
                repo.update_generation_run(run)
                repo.update_ticket(ticket)
                return

            drafts = result.get("drafts", {}) or {}
            draft_iterations = result.get("draft_iterations", {}) or {}
            evaluations = result.get("evaluations", {}) or {}
            approved = result.get("approved", {}) or {}

            from app.domains.rfp.models import RfpSectionDraft, RfpSectionEvaluation

            for dept, content in drafts.items():
                iteration = int(draft_iterations.get(dept, 1))
                existing = repo.get_draft(ticket.id, dept, iteration)
                if existing is None:
                    draft = RfpSectionDraft(
                        ticket_id=ticket.id,
                        department_id=dept,
                        version=iteration,
                        iteration=iteration,
                        content=content,
                        generator_id=f"{dept}-section-generator",
                        model=settings.generation_model,
                        prompt_hash=None,
                        status="evaluated" if dept in evaluations else "draft",
                    )
                    repo.save_draft(draft)
                ev = evaluations.get(dept)
                if ev is not None:
                    d = repo.get_draft(ticket.id, dept, iteration)
                    eval_row = RfpSectionEvaluation(
                        ticket_id=ticket.id,
                        department_id=dept,
                        draft_id=d.id if d else None,
                        iteration=int(ev.get("iteration", iteration)),
                        readability=ev.get("readability", {}),
                        relevance=ev.get("relevance", {}),
                        compliance=ev.get("compliance", {}),
                        overall_pass=bool(ev.get("overall_pass", False)),
                        feedback_for_generator=str(ev.get("feedback_for_generator", "")),
                    )
                    repo.save_evaluation(eval_row)

            run.current_iteration = max(draft_iterations.values()) if draft_iterations else run.current_iteration
            run.all_sections_approved = all(approved.get(d, False) for d in active)
            run.needs_human_review = result.get("outcome") == "needs_human_review"
            run.needs_human_review_reason = "iteration_limit_exhausted" if run.needs_human_review else None
            run.global_compliance = result.get("global_compliance")
            run.status = "completed"
            run.completed_at = _now()
            repo.update_generation_run(run)

            from app.domains.rfp.models import RfpGenerationHandoff

            sections_payload = []
            for dept in active:
                iteration = int(draft_iterations.get(dept, 1))
                d = repo.get_draft(ticket.id, dept, iteration)
                ev = evaluations.get(dept, {})
                sections_payload.append(
                    {
                        "department_id": dept,
                        "draft_id": str(d.id) if d else None,
                        "version": iteration,
                        "content": drafts.get(dept, ""),
                        "evaluation_result": ev,
                        "approval_status": "pendiente",
                    }
                )
            gen_handoff = RfpGenerationHandoff(
                ticket_id=ticket.id,
                sections=sections_payload,
                global_compliance=run.global_compliance,
                open_questions=list(result.get("open_questions", [])),
                requires_ceo_approval=bool(result.get("requires_ceo_approval", False)),
            )
            repo.save_generation_handoff(gen_handoff)

            if run.needs_human_review:
                ticket.status = "needs_human_review"
            else:
                ticket.status = "en_evaluación"
            ticket.processing_completed_at = _now()
            ticket.error_code = None
            ticket.error_detail = None
            repo.update_ticket(ticket)

        except Exception as exc:  # noqa: BLE001
            code = "processing_failed"
            run.status = "failed"
            run.error_code = code
            run.error_detail = str(exc)[:1000]
            ticket.error_code = code
            ticket.error_detail = str(exc)[:1000]
            ticket.failed_at = _now()
            repo.update_generation_run(run)
            repo.update_ticket(ticket)


# ---------- Parte 3: aprobación humana ----------

import json as _json
import os as _os
from pathlib import Path as _Path


def get_rfp_checkpointer():
    db_url = _os.getenv("DATABASE_URL", "").strip()
    if db_url.startswith("postgres"):
        from langgraph.checkpoint.postgres import PostgresSaver

        if db_url.startswith("postgresql+psycopg2://"):
            db_url = db_url.replace("postgresql+psycopg2://", "postgresql://", 1)
        return PostgresSaver.from_conn_string(db_url)

    from langgraph.checkpoint.sqlite import SqliteSaver

    path = _os.getenv("RFP_CHECKPOINT_DB", str(_Path(__file__).resolve().parents[5] / "data" / "rfp_checkpoints.sqlite"))
    _Path(path).parent.mkdir(parents=True, exist_ok=True)
    return SqliteSaver.from_conn_string(path)


def init_rfp_checkpoints() -> None:
    if _os.getenv("DATABASE_URL", "").strip().startswith("postgres"):
        with get_rfp_checkpointer() as saver:
            saver.setup()


def _approver_map() -> dict[str, list[str]]:
    raw = _os.getenv("RFP_APPROVER_MAP", "").strip()
    if not raw:
        return {}
    try:
        data = _json.loads(raw)
        if isinstance(data, dict):
            return {str(k): [str(x) for x in (v or [])] for k, v in data.items()}
    except _json.JSONDecodeError:
        pass
    return {}


def is_authorized_approver(current_user: dict, department_id: str, session=None) -> bool:
    if str(current_user.get("role", "")).lower() == "admin":
        return True
    user_uuid = str(current_user.get("uuid", ""))
    allowed = list(_approver_map().get(department_id, []))
    if session is not None:
        try:
            repo = RfpRepository(session)
            for row in repo.list_department_approvers(department_id):
                allowed.append(str(row.user_uuid))
        except Exception:  # noqa: BLE001
            pass
    return user_uuid in allowed


def start_rfp_approval(session, ticket_id: uuid.UUID) -> tuple[RfpTicket, "RfpApprovalRun"]:
    from app.domains.rfp.models import RfpApprovalRun, RfpGenerationHandoff

    ticket = get_ticket(session, ticket_id)
    repo = RfpRepository(session)
    run = repo.get_approval_run(ticket_id)
    handoff = repo.get_generation_handoff(ticket_id)
    if handoff is None:
        raise ValueError("Missing Parte 2 generation handoff.")

    active = []
    for s in (handoff.sections or []):
        if isinstance(s, dict) and s.get("department_id"):
            active.append(str(s.get("department_id")))
    if not active:
        raise ValueError("Generation handoff has no active departments.")

    if run is None:
        run = RfpApprovalRun(
            ticket_id=ticket.id,
            thread_id=f"rfp-{ticket.id}",
            status="pendiente",
            active_departments=active,
            requires_ceo_approval=bool(handoff.requires_ceo_approval),
            max_correction_cycles=3,
        )
        run = repo.create_approval_run(run)

    if ticket.status in ("analisis_completo", "generando_borrador", "en_evaluación", "needs_human_review", "esperando_aprobación"):
        ticket.status = "esperando_aprobación"
        ticket.updated_at = _now()
        repo.update_ticket(ticket)

    return ticket, run


def _load_approval_state(session, ticket_id: uuid.UUID):
    repo = RfpRepository(session)
    ticket = get_ticket(session, ticket_id)
    handoff = repo.get_handoff(ticket_id)
    gen_handoff = repo.get_generation_handoff(ticket_id)
    metadata = {}
    meta = repo.get_metadata(ticket_id)
    if meta is not None:
        metadata = meta.fields or {}
    aspects_by_department = _group_aspects(session, ticket_id)
    active = []
    if gen_handoff is not None:
        for s in (gen_handoff.sections or []):
            if isinstance(s, dict) and s.get("department_id"):
                active.append(str(s.get("department_id")))
    run = repo.get_approval_run(ticket_id)
    if run is not None and run.active_departments:
        active = run.active_departments

    # drafts/versiones/evaluaciones más recientes
    drafts = {}
    versions = {}
    evaluations = {}
    for d in active:
        ds = [x for x in repo.list_drafts(ticket_id) if x.department_id == d]
        if ds:
            latest = max(ds, key=lambda x: x.version)
            drafts[d] = latest.content
            versions[d] = latest.version
        evs = [x for x in repo.list_evaluations(ticket_id) if x.department_id == d]
        if evs:
            latest_ev = max(evs, key=lambda x: x.iteration)
            evaluations[d] = {
                "section_id": latest_ev.department_id,
                "department_id": latest_ev.department_id,
                "iteration": latest_ev.iteration,
                "readability": latest_ev.readability,
                "relevance": latest_ev.relevance,
                "compliance": latest_ev.compliance,
                "overall_pass": latest_ev.overall_pass,
                "feedback_for_generator": latest_ev.feedback_for_generator,
            }

    requires_ceo = bool(gen_handoff.requires_ceo_approval) if gen_handoff is not None else False
    global_compliance = gen_handoff.global_compliance if gen_handoff is not None else None
    open_questions = list(gen_handoff.open_questions or []) if gen_handoff is not None else []

    return ticket, run, active, metadata, aspects_by_department, drafts, versions, evaluations, requires_ceo, global_compliance, open_questions, gen_handoff


def process_rfp_approval(ticket_id: uuid.UUID) -> None:
    try:
        engine = get_db_engine()
    except RuntimeError:
        return
    with Session(engine) as session:
        ticket, run, active, metadata, aspects, drafts, versions, evaluations, requires_ceo, global_compliance, open_questions, gen_handoff = _load_approval_state(session, ticket_id)
        if ticket is None or run is None:
            return
        if run.status in ("completado", "failed"):
            return

        repo = RfpRepository(session)
        run.status = "running"
        run.error_code = None
        run.error_detail = None
        repo.update_approval_run(run)

        ticket.status = "esperando_aprobación"
        repo.update_ticket(ticket)

        try:
            import sys
            from pathlib import Path

            repo_root = Path(__file__).resolve().parents[5]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))

            from data.pipelines.rfp_approval import run_rfp_approval
            with _checkpointer_context(get_rfp_checkpointer()) as saver:
                result, _ = run_rfp_approval(
                    ticket_id=str(ticket.id),
                    active_departments=active,
                    metadata=metadata,
                    aspects_by_department=aspects,
                    drafts=drafts,
                    draft_versions=versions,
                    evaluations=evaluations,
                    requires_ceo_approval=requires_ceo,
                    global_compliance=global_compliance or {},
                    open_questions=open_questions,
                    max_correction_cycles=run.max_correction_cycles,
                    checkpointer=saver,
                )

            # persist approvals from state
            approvals = result.get("approvals", {}) or {}
            for dept, info in approvals.items():
                if not isinstance(info, dict):
                    continue
                if info.get("decision") is None and info.get("status") == "pendiente":
                    continue
                # only persist decided approvals
                if info.get("status") == "pendiente":
                    continue
                version = info.get("version")
                if version is None and dept != "ceo":
                    version = versions.get(dept, 1)
                if dept == "ceo":
                    continue
                draft_id = None
                d = repo.get_draft(ticket.id, dept, int(version)) if version is not None else None
                if d is not None:
                    draft_id = d.id
                decision = info.get("decision") or ("approve" if info.get("status") == "aprobado" else "reject")
                approval_row = RfpHumanApproval(
                    ticket_id=ticket.id,
                    department_id=dept,
                    draft_id=draft_id,
                    version=int(version) if version is not None else 1,
                    decision=str(decision),
                    comment=str(info.get("comment", "") or ""),
                    approver_uuid=str(info.get("approver_uuid", "") or ""),
                )
                repo.save_human_approval(approval_row)

            # conflicts persistence (best-effort, avoid duplicates by trigger+dept)
            for c in (result.get("conflicts") or []):
                existing = [x for x in repo.list_conflicts(ticket.id) if x.trigger_id == c.get("trigger_id") and x.departments == c.get("departments")]
                if not existing:
                    repo.save_conflict(
                        RfpConflict(
                            ticket_id=ticket.id,
                            trigger_id=str(c.get("trigger_id")),
                            departments=list(c.get("departments", [])),
                            summary=str(c.get("summary", "")),
                            arbiter=str(c.get("arbiter", "")),
                            status=str(c.get("status", "open")),
                        )
                    )

            run.correction_cycle = int(result.get("correction_cycle", run.correction_cycle))
            run.conflicts = list(result.get("conflicts", []) or [])
            run.sections_to_correct = list(result.get("sections_to_correct", []) or [])
            run.requires_ceo_approval = requires_ceo
            run.ceo_approved = bool((result.get("approvals", {}) or {}).get("ceo", {}).get("status") == "aprobado")

            if "__interrupt__" in result:
                run.status = "esperando_aprobación"
                run.error_code = None
                run.error_detail = None
                repo.update_approval_run(run)
                ticket.status = "esperando_aprobación"
                repo.update_ticket(ticket)
                return

            outcome = result.get("outcome")
            if outcome == "terminado":
                # save final document
                from app.domains.rfp.models import RfpFinalDocument

                content = result.get("final_document_content", "")
                sections = result.get("final_document_sections", [])
                # idempotency: only if not exists
                existing_doc = repo.get_final_document(ticket.id)
                if existing_doc is None:
                    doc = RfpFinalDocument(
                        ticket_id=ticket.id,
                        content=content,
                        file_reference="",
                        sections=sections,
                        total_estimated_value=_estimate_value_from_metadata(metadata),
                    )
                    doc = repo.save_final_document(doc)
                    run.final_document_id = doc.id
                else:
                    run.final_document_id = existing_doc.id

                run.status = "completado"
                run.completed_at = _now()
                repo.update_approval_run(run)
                ticket.status = "terminado"
                ticket.processing_completed_at = _now()
                repo.update_ticket(ticket)
                return

            if outcome in ("rechazado", "agotado"):
                run.status = outcome
                repo.update_approval_run(run)
                ticket.status = "needs_human_review"
                repo.update_ticket(ticket)
                return

            # default: still waiting
            run.status = "esperando_aprobación"
            repo.update_approval_run(run)
            ticket.status = "esperando_aprobación"
            repo.update_ticket(ticket)

        except Exception as exc:  # noqa: BLE001
            run.status = "failed"
            run.error_code = "processing_failed"
            run.error_detail = str(exc)[:1000]
            ticket.error_code = "processing_failed"
            ticket.error_detail = str(exc)[:1000]
            ticket.failed_at = _now()
            repo.update_approval_run(run)
            repo.update_ticket(ticket)


def _estimate_value_from_metadata(metadata: dict[str, Any]) -> Optional[float]:
    from data.process.rfp_generation import estimate_value_usd

    return estimate_value_usd(metadata or {})


def _resume_approval_graph(ticket_id: uuid.UUID, decision_payload: dict[str, Any]) -> dict[str, Any]:
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[5]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from data.pipelines.rfp_approval import build_graph
    from langgraph.types import Command

    checkpointer = get_rfp_checkpointer()
    with _checkpointer_context(checkpointer) as saver:
        graph = build_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": f"rfp-{ticket_id}"}}
        state = graph.get_state(config)
        # map by department: use the interrupt whose payload department matches
        target_dept = decision_payload.get("department_id")
        target_id = None
        for t in state.tasks:
            for iv in t.interrupts:
                val = iv.value if hasattr(iv, "value") else {}
                if isinstance(val, dict) and val.get("department_id") == target_dept:
                    target_id = iv.id
        if target_id is None:
            raise ValueError("No hay una aprobación pendiente para ese departamento.")
        result = graph.invoke(Command(resume={target_id: decision_payload}), config)
        return dict(result)


def _checkpointer_context(saver):
    # saver may already be a context manager or instance
    class _Ctx:
        def __enter__(self):
            return saver
        def __exit__(self, *args):
            return False
    # If saver has __enter__, use it
    if hasattr(saver, "__enter__"):
        return saver
    return _Ctx()


def submit_approval_decision(
    session,
    ticket_id: uuid.UUID,
    department_id: str,
    decision: str,
    comment: str,
    version: Optional[int],
    current_user: dict,
) -> dict[str, Any]:
    import uuid as _uuid

    from app.domains.rfp.errors import RfpNotFoundError, RfpValidationError

    ticket = get_ticket(session, ticket_id)
    repo = RfpRepository(session)
    run = repo.get_approval_run(ticket_id)
    if run is None:
        raise RfpNotFoundError("Approval run not found.")
    if department_id not in (run.active_departments or []) and department_id != "ceo":
        raise RfpValidationError("Department not active for this ticket.")
    if department_id == "ceo" and not run.requires_ceo_approval:
        raise RfpValidationError("CEO approval not required.")

    if not is_authorized_approver(current_user, department_id, session=session):
        raise RfpValidationError("User not authorized to approve this department.")

    decision_norm = str(decision).strip().lower()
    if decision_norm not in ("approve", "reject", "request_changes"):
        raise RfpValidationError("Invalid decision.")
    if decision_norm in ("reject", "request_changes") and not (comment or "").strip():
        raise RfpValidationError("Comment required for reject/request_changes.")

    # version resolution
    if department_id != "ceo":
        drafts = [d for d in repo.list_drafts(ticket_id) if d.department_id == department_id]
        if not drafts:
            raise RfpValidationError("No draft for department.")
        latest = max(drafts, key=lambda x: x.version)
        if version is None:
            version = latest.version
        if int(version) != latest.version:
            raise RfpValidationError("Stale version.")

    # idempotency: if already decided with same version+decision, return
    existing = repo.get_human_approval(ticket_id, department_id, int(version)) if (department_id != "ceo" and version is not None) else None
    if existing is not None and existing.resumed_at is not None:
        return {"ticket_id": ticket_id, "department_id": department_id, "decision": existing.decision, "version": existing.version, "status": "already_processed"}

    # build decision payload for graph
    decision_payload = {
        "department_id": department_id,
        "decision": decision_norm,
        "comment": comment or "",
        "approver_uuid": str(current_user.get("uuid", "")),
        "version": version,
    }

    result = _resume_approval_graph(str(ticket.id), decision_payload)

    # persist approval row
    if department_id != "ceo":
        from app.domains.rfp.models import RfpHumanApproval

        draft = repo.get_draft(ticket.id, department_id, int(version))
        approval_row = RfpHumanApproval(
            ticket_id=ticket.id,
            department_id=department_id,
            draft_id=draft.id if draft else None,
            version=int(version),
            decision=decision_norm,
            comment=comment or "",
            approver_uuid=str(current_user.get("uuid", "")),
            resumed_at=_now(),
        )
        saved = repo.save_human_approval(approval_row)
        # mark resumed_at
        saved.resumed_at = _now()
        repo.session.add(saved)
        repo.session.commit()

    # update run/ticket based on result
    run = repo.get_approval_run(ticket_id)
    if run is not None:
        run.correction_cycle = int(result.get("correction_cycle", run.correction_cycle))
        run.conflicts = list(result.get("conflicts", run.conflicts) or [])
        run.sections_to_correct = list(result.get("sections_to_correct", run.sections_to_correct) or [])
        run.ceo_approved = bool((result.get("approvals", {}) or {}).get("ceo", {}).get("status") == "aprobado")

        if "__interrupt__" in result:
            run.status = "esperando_aprobación"
            repo.update_approval_run(run)
            ticket.status = "esperando_aprobación"
            repo.update_ticket(ticket)
        elif result.get("outcome") == "terminado":
            from app.domains.rfp.models import RfpFinalDocument

            content = result.get("final_document_content", "")
            sections = result.get("final_document_sections", [])
            existing_doc = repo.get_final_document(ticket.id)
            if existing_doc is None:
                doc = RfpFinalDocument(
                    ticket_id=ticket.id,
                    content=content,
                    file_reference="",
                    sections=sections,
                    total_estimated_value=_estimate_value_from_metadata(metadata if False else (repo.get_metadata(ticket.id).fields if repo.get_metadata(ticket.id) else {})),
                )
                doc = repo.save_final_document(doc)
                run.final_document_id = doc.id
            else:
                run.final_document_id = existing_doc.id
            run.status = "completado"
            run.completed_at = _now()
            repo.update_approval_run(run)
            ticket.status = "terminado"
            ticket.processing_completed_at = _now()
            repo.update_ticket(ticket)
        elif result.get("outcome") in ("rechazado", "agotado"):
            run.status = str(result.get("outcome"))
            repo.update_approval_run(run)
            ticket.status = "needs_human_review"
            repo.update_ticket(ticket)
        else:
            run.status = "esperando_aprobación"
            repo.update_approval_run(run)
            ticket.status = "esperando_aprobación"
            repo.update_ticket(ticket)

    return {"ticket_id": ticket_id, "department_id": department_id, "decision": decision_norm, "version": version, "status": "processed"}


def assign_department_approver(session, department_id: str, user_uuid: str, responsible_name: str, current_user: dict):
    if str(current_user.get("role", "")).lower() != "admin":
        raise ValueError("Only admins can assign approvers.")
    from app.domains.rfp.models import RfpDepartmentApprover

    repo = RfpRepository(session)
    row = RfpDepartmentApprover(
        department_id=department_id,
        user_uuid=user_uuid,
        responsible_name=responsible_name,
    )
    return repo.save_department_approver(row)


def list_department_approvers(session, department_id: str):
    repo = RfpRepository(session)
    return repo.list_department_approvers(department_id)
