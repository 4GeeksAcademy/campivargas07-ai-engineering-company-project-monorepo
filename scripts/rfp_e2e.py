"""Reproducible E2E flow for RFP Parts 1-3.

By default runs offline with a fake generator (no external providers).
Use --live to use RFP_GENERATION_* from the environment (consumes provider quota).
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "services" / "api"))

import io
from pypdf import PdfWriter

from app.database import init_db
from sqlmodel import Session

from app.domains.rfp.service import get_db_engine, start_rfp_approval, process_rfp_approval, submit_approval_decision
from app.domains.rfp.models import RfpTicket, RfpHandoff, RfpGenerationHandoff, RfpSectionDraft, RfpSectionEvaluation


def make_pdf() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    if not args.live:
        os.environ.setdefault("RFP_GENERATION_URL", "https://example.com/v1/chat/completions")
        os.environ.setdefault("RFP_GENERATION_MODEL", "test-model")
        os.environ.setdefault("RFP_GENERATION_API_KEY", "test-key")
        import data.process.rfp_generation as gen

        def fake(department_id, metadata, aspects, settings, feedback=None, client=None):
            return "Seccion " + department_id + ". Calidad consistente, experiencia calida y velocidad de servicio. Validez de la oferta: 30 dias desde su emision. Precio: 1000 COP y 1 USD."

        gen.generate_section = fake

    # Use isolated SQLite
    os.environ.setdefault("DATABASE_URL", "")
    engine = get_db_engine() if os.getenv("DATABASE_URL") else None
    if engine is None:
        from sqlalchemy import create_engine

        engine = create_engine("sqlite:///./rfp_e2e.sqlite", connect_args={"check_same_thread": False})
        init_db(bind_engine=engine)

    ticket_id = uuid.uuid4()
    with Session(engine) as session:
        ticket = RfpTicket(id=ticket_id, status="en_evaluación", original_filename="e2e.pdf", storage_path="/tmp/e2e.pdf", idempotency_key=str(uuid.uuid4()))
        session.add(ticket)
        session.commit()
        handoff = RfpHandoff(ticket_id=ticket_id, key_aspects=[{"department": "marketing", "aspect": "Términos", "detail": "d"}], workstreams=[{"department": "marketing", "status": "pendiente"}])
        session.add(handoff)
        session.commit()
        gen_handoff = RfpGenerationHandoff(ticket_id=ticket_id, sections=[{"department_id": "marketing", "draft_id": None, "version": 1, "content": "draft", "evaluation_result": {"overall_pass": True}, "approval_status": "pendiente"}], global_compliance={"pass": True, "rule_ids": [], "violations": [], "details": "ok"}, open_questions=[], requires_ceo_approval=False)
        session.add(gen_handoff)
        session.commit()
        draft = RfpSectionDraft(ticket_id=ticket_id, department_id="marketing", version=1, iteration=1, content="draft content", generator_id="marketing-section-generator", model="test-model", status="evaluated")
        session.add(draft)
        session.commit()
        ev = RfpSectionEvaluation(ticket_id=ticket_id, department_id="marketing", draft_id=draft.id, iteration=1, readability={}, relevance={}, compliance={}, overall_pass=True, feedback_for_generator="")
        session.add(ev)
        session.commit()

    # Part 3
    with Session(engine) as session:
        t, run = start_rfp_approval(session, ticket_id)
        print("approval started:", t.status, run.id)

    process_rfp_approval(ticket_id)

    # programmatic approval
    with Session(engine) as session:
        from app.domains.auth.dependencies import get_current_user

    # We don't have JWT here; use a fake admin user dict
    fake_user = {"uuid": str(uuid.uuid4()), "role": "admin", "is_active": True}
    # register approver mapping via env not needed for admin
    res = submit_approval_decision(
        session=Session(engine),
        ticket_id=ticket_id,
        department_id="marketing",
        decision="approve",
        comment="",
        version=1,
        current_user=fake_user,
    )
    print("decision:", res)

    process_rfp_approval(ticket_id)

    with Session(engine) as session:
        from app.domains.rfp.repository import RfpRepository

        repo = RfpRepository(session)
        doc = repo.get_final_document(ticket_id)
        if doc:
            print("FINAL DOCUMENT:\n", doc.content[:500])
        else:
            print("No final document yet")


if __name__ == "__main__":
    main()
PY
echo done