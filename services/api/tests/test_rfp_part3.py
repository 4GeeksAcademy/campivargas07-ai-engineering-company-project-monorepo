"""API tests for RFP human approval and completion (Parte 3)."""
from __future__ import annotations

import io
import os
import os
import uuid

import pytest
from pypdf import PdfWriter
from sqlmodel import Session

from app.database import init_db
from app.domains.rfp.models import RfpGenerationHandoff, RfpSectionDraft, RfpSectionEvaluation, RfpTicket
from app.domains.rfp.service import get_db_engine as _orig_engine


def _make_pdf_bytes(text: str = "Sample RFP content") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def rfp_approval_env(monkeypatch, sqlite_engine):
    monkeypatch.setenv("RFP_GENERATION_URL", "https://example.com/v1/chat/completions")
    monkeypatch.setenv("RFP_GENERATION_MODEL", "test-model")
    monkeypatch.setenv("RFP_GENERATION_API_KEY", "test-key")
    monkeypatch.setenv("RFP_MAX_ITERATIONS", "1")
    monkeypatch.setenv("RFP_APPROVER_MAP", '{}')
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    from langgraph.checkpoint.memory import MemorySaver

    ms = MemorySaver()
    monkeypatch.setattr("app.domains.rfp.service.get_rfp_checkpointer", lambda: ms)

    import data.process.rfp_generation as gen

    def fake_generate_section(department_id, metadata, aspects, settings, feedback=None, client=None):
        return "Esta es una seccion. " * 20 + "Calidad consistente, experiencia calida y velocidad de servicio. Validez de la oferta: 30 dias desde su emision. Precio: 1000 COP y 1 USD."

    monkeypatch.setattr(gen, "generate_section", fake_generate_section)


def _seed_ticket_with_generation(ticket_id, sqlite_engine):
    init_db(bind_engine=sqlite_engine)
    with Session(sqlite_engine) as session:
        ticket = RfpTicket(
            id=ticket_id,
            status="en_evaluación",
            original_filename="sample.pdf",
            storage_path="/tmp/sample.pdf",
            idempotency_key=str(uuid.uuid4()),
        )
        session.add(ticket)
        session.commit()
    with Session(sqlite_engine) as session:
        handoff = RfpGenerationHandoff(
            ticket_id=ticket_id,
            sections=[{"department_id": "marketing", "draft_id": None, "version": 1, "content": "draft", "evaluation_result": {"overall_pass": True}, "approval_status": "pendiente"}],
            global_compliance={"pass": True, "rule_ids": [], "violations": [], "details": "ok"},
            open_questions=[],
            requires_ceo_approval=False,
        )
        session.add(handoff)
        session.commit()
        draft = RfpSectionDraft(
            ticket_id=ticket_id,
            department_id="marketing",
            version=1,
            iteration=1,
            content="draft content",
            generator_id="marketing-section-generator",
            model="test-model",
            status="evaluated",
        )
        session.add(draft)
        session.commit()
        ev = RfpSectionEvaluation(
            ticket_id=ticket_id,
            department_id="marketing",
            draft_id=draft.id,
            iteration=1,
            readability={},
            relevance={},
            compliance={},
            overall_pass=True,
            feedback_for_generator="",
        )
        session.add(ev)
        session.commit()


def test_start_approval_and_list(client, auth_headers, sqlite_engine):
    ticket_id = uuid.uuid4()
    _seed_ticket_with_generation(ticket_id, sqlite_engine)
    res = client.post(f"/rfp-requests/{ticket_id}/approval/start", headers=auth_headers)
    assert res.status_code == 202
    import time
    for _ in range(20):
        r = client.get(f"/rfp-requests/{ticket_id}/approvals", headers=auth_headers).json()
        if r.get("approvals") is not None:
            break
        time.sleep(0.1)
    r = client.get(f"/rfp-requests/{ticket_id}/approvals", headers=auth_headers).json()
    assert r["ticket_id"] == str(ticket_id)


def test_submit_decision_and_final_document(client, auth_headers, sqlite_engine, test_db):
    ticket_id = uuid.uuid4()
    _seed_ticket_with_generation(ticket_id, sqlite_engine)
    # create an admin user? Use current auth_headers from fixture (role user). Make approver map include user uuid.
    # Get current user uuid
    me = client.get("/auth/me", headers=auth_headers).json()
    user_uuid = me["user"]["uuid"]
    os.environ["RFP_APPROVER_MAP"] = '{"marketing": ["%s"]}' % user_uuid
    # reload map is read at call time, ok

    res = client.post(f"/rfp-requests/{ticket_id}/approval/start", headers=auth_headers)
    assert res.status_code == 202
    import time
    for _ in range(30):
        r = client.get(f"/rfp-requests/{ticket_id}/approvals", headers=auth_headers).json()
        # try submit
        dres = client.post(
            f"/rfp-requests/{ticket_id}/approvals/marketing",
            headers=auth_headers,
            json={"decision": "approve", "comment": "", "version": 1},
        )
        if dres.status_code in (200,):
            break
        time.sleep(0.1)

    # final document should be available
    for _ in range(30):
        fd = client.get(f"/rfp-requests/{ticket_id}/final-document", headers=auth_headers)
        if fd.status_code == 200:
            break
        time.sleep(0.1)
    fd = client.get(f"/rfp-requests/{ticket_id}/final-document", headers=auth_headers)
    assert fd.status_code == 200
    assert "Propuesta RFP" in fd.json()["content"]