"""RFP intake service: ticket lifecycle, async processing, persistence."""
from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

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
