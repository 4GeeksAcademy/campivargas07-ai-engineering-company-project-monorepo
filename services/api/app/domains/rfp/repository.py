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
