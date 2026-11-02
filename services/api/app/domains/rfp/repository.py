"""Persistence helpers for RFP intake (PostgreSQL/Supabase via SQLModel)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from .models import (
    RfpClassification,
    RfpDepartmentAspect,
    RfpDepartmentContact,
    RfpHandoff,
    RfpMetadata,
    RfpReadabilityMetrics,
    RfpSynthesis,
    RfpTicket,
)


class RfpRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_ticket(self, ticket: RfpTicket) -> RfpTicket:
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)
        return ticket

    def get_ticket(self, ticket_id: uuid.UUID) -> Optional[RfpTicket]:
        return self.session.get(RfpTicket, ticket_id)

    def get_ticket_by_idempotency(self, key: str) -> Optional[RfpTicket]:
        stmt = select(RfpTicket).where(RfpTicket.idempotency_key == key)
        return self.session.exec(stmt).first()

    def update_ticket(self, ticket: RfpTicket) -> RfpTicket:
        ticket.updated_at = datetime.now(timezone.utc)
        self.session.add(ticket)
        self.session.commit()
        self.session.refresh(ticket)
        return ticket

    def save_metadata(self, metadata: RfpMetadata) -> RfpMetadata:
        self.session.add(metadata)
        self.session.commit()
        self.session.refresh(metadata)
        return metadata

    def get_metadata(self, ticket_id: uuid.UUID) -> Optional[RfpMetadata]:
        stmt = select(RfpMetadata).where(RfpMetadata.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def save_readability(self, metric: RfpReadabilityMetrics) -> RfpReadabilityMetrics:
        self.session.add(metric)
        self.session.commit()
        self.session.refresh(metric)
        return metric

    def list_readability(self, ticket_id: uuid.UUID) -> list[RfpReadabilityMetrics]:
        stmt = select(RfpReadabilityMetrics).where(RfpReadabilityMetrics.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def save_classification(self, classification: RfpClassification) -> RfpClassification:
        self.session.add(classification)
        self.session.commit()
        self.session.refresh(classification)
        return classification

    def get_classification(self, ticket_id: uuid.UUID) -> Optional[RfpClassification]:
        stmt = select(RfpClassification).where(RfpClassification.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def add_aspect(self, aspect: RfpDepartmentAspect) -> RfpDepartmentAspect:
        self.session.add(aspect)
        self.session.commit()
        self.session.refresh(aspect)
        return aspect

    def list_aspects(self, ticket_id: uuid.UUID) -> list[RfpDepartmentAspect]:
        stmt = select(RfpDepartmentAspect).where(RfpDepartmentAspect.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def add_contact(self, contact: RfpDepartmentContact) -> RfpDepartmentContact:
        self.session.add(contact)
        self.session.commit()
        self.session.refresh(contact)
        return contact

    def list_contacts(self, ticket_id: uuid.UUID) -> list[RfpDepartmentContact]:
        stmt = select(RfpDepartmentContact).where(RfpDepartmentContact.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def save_synthesis(self, synthesis: RfpSynthesis) -> RfpSynthesis:
        self.session.add(synthesis)
        self.session.commit()
        self.session.refresh(synthesis)
        return synthesis

    def get_synthesis(self, ticket_id: uuid.UUID) -> Optional[RfpSynthesis]:
        stmt = select(RfpSynthesis).where(RfpSynthesis.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def save_handoff(self, handoff: RfpHandoff) -> RfpHandoff:
        self.session.add(handoff)
        self.session.commit()
        self.session.refresh(handoff)
        return handoff

    def get_handoff(self, ticket_id: uuid.UUID) -> Optional[RfpHandoff]:
        stmt = select(RfpHandoff).where(RfpHandoff.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def update_handoff(self, handoff: RfpHandoff) -> RfpHandoff:
        self.session.add(handoff)
        self.session.commit()
        self.session.refresh(handoff)
        return handoff

    # --- Parte 2: generation run ---
    def get_generation_run(self, ticket_id: uuid.UUID) -> Optional["RfpGenerationRun"]:
        from .models import RfpGenerationRun

        stmt = select(RfpGenerationRun).where(RfpGenerationRun.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def create_generation_run(self, run: "RfpGenerationRun") -> "RfpGenerationRun":
        from .models import RfpGenerationRun

        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def update_generation_run(self, run: "RfpGenerationRun") -> "RfpGenerationRun":
        from .models import RfpGenerationRun

        run.updated_at = datetime.now(timezone.utc)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    # --- drafts ---
    def get_draft(self, ticket_id: uuid.UUID, department_id: str, version: int) -> Optional["RfpSectionDraft"]:
        from .models import RfpSectionDraft

        stmt = select(RfpSectionDraft).where(
            RfpSectionDraft.ticket_id == ticket_id,
            RfpSectionDraft.department_id == department_id,
            RfpSectionDraft.version == version,
        )
        return self.session.exec(stmt).first()

    def list_drafts(self, ticket_id: uuid.UUID) -> list["RfpSectionDraft"]:
        from .models import RfpSectionDraft

        stmt = select(RfpSectionDraft).where(RfpSectionDraft.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def save_draft(self, draft: "RfpSectionDraft") -> "RfpSectionDraft":
        from .models import RfpSectionDraft

        existing = self.get_draft(draft.ticket_id, draft.department_id, draft.version)
        if existing is not None:
            return existing
        self.session.add(draft)
        self.session.commit()
        self.session.refresh(draft)
        return draft

    # --- evaluations ---
    def list_evaluations(self, ticket_id: uuid.UUID) -> list["RfpSectionEvaluation"]:
        from .models import RfpSectionEvaluation

        stmt = select(RfpSectionEvaluation).where(RfpSectionEvaluation.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def save_evaluation(self, evaluation: "RfpSectionEvaluation") -> "RfpSectionEvaluation":
        from .models import RfpSectionEvaluation

        self.session.add(evaluation)
        self.session.commit()
        self.session.refresh(evaluation)
        return evaluation

    # --- generation handoff ---
    def get_generation_handoff(self, ticket_id: uuid.UUID) -> Optional["RfpGenerationHandoff"]:
        from .models import RfpGenerationHandoff

        stmt = select(RfpGenerationHandoff).where(RfpGenerationHandoff.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def save_generation_handoff(self, handoff: "RfpGenerationHandoff") -> "RfpGenerationHandoff":
        from .models import RfpGenerationHandoff

        existing = self.get_generation_handoff(handoff.ticket_id)
        if existing is not None:
            existing.sections = handoff.sections
            existing.global_compliance = handoff.global_compliance
            existing.open_questions = handoff.open_questions
            existing.requires_ceo_approval = handoff.requires_ceo_approval
            existing.consumed_at = handoff.consumed_at
            existing.consumed_by = handoff.consumed_by
            self.session.add(existing)
            self.session.commit()
            self.session.refresh(existing)
            return existing
        self.session.add(handoff)
        self.session.commit()
        self.session.refresh(handoff)
        return handoff

    # --- Parte 3: approval run ---
    def get_approval_run(self, ticket_id: uuid.UUID) -> Optional["RfpApprovalRun"]:
        from .models import RfpApprovalRun

        stmt = select(RfpApprovalRun).where(RfpApprovalRun.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def create_approval_run(self, run: "RfpApprovalRun") -> "RfpApprovalRun":
        from .models import RfpApprovalRun

        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    def update_approval_run(self, run: "RfpApprovalRun") -> "RfpApprovalRun":
        from .models import RfpApprovalRun

        run.updated_at = datetime.now(timezone.utc)
        self.session.add(run)
        self.session.commit()
        self.session.refresh(run)
        return run

    # --- human approvals ---
    def list_human_approvals(self, ticket_id: uuid.UUID) -> list["RfpHumanApproval"]:
        from .models import RfpHumanApproval

        stmt = select(RfpHumanApproval).where(RfpHumanApproval.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def get_human_approval(self, ticket_id: uuid.UUID, department_id: str, version: int) -> Optional["RfpHumanApproval"]:
        from .models import RfpHumanApproval

        stmt = select(RfpHumanApproval).where(
            RfpHumanApproval.ticket_id == ticket_id,
            RfpHumanApproval.department_id == department_id,
            RfpHumanApproval.version == version,
        )
        return self.session.exec(stmt).first()

    def save_human_approval(self, approval: "RfpHumanApproval") -> "RfpHumanApproval":
        from .models import RfpHumanApproval

        existing = self.get_human_approval(approval.ticket_id, approval.department_id, approval.version)
        if existing is not None:
            return existing
        self.session.add(approval)
        self.session.commit()
        self.session.refresh(approval)
        return approval

    # --- conflicts ---
    def list_conflicts(self, ticket_id: uuid.UUID) -> list["RfpConflict"]:
        from .models import RfpConflict

        stmt = select(RfpConflict).where(RfpConflict.ticket_id == ticket_id)
        return list(self.session.exec(stmt).all())

    def save_conflict(self, conflict: "RfpConflict") -> "RfpConflict":
        from .models import RfpConflict

        self.session.add(conflict)
        self.session.commit()
        self.session.refresh(conflict)
        return conflict

    # --- final document ---
    def get_final_document(self, ticket_id: uuid.UUID) -> Optional["RfpFinalDocument"]:
        from .models import RfpFinalDocument

        stmt = select(RfpFinalDocument).where(RfpFinalDocument.ticket_id == ticket_id)
        return self.session.exec(stmt).first()

    def save_final_document(self, doc: "RfpFinalDocument") -> "RfpFinalDocument":
        from .models import RfpFinalDocument

        existing = self.get_final_document(doc.ticket_id)
        if existing is not None:
            return existing
        self.session.add(doc)
        self.session.commit()
        self.session.refresh(doc)
        return doc
