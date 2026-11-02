"""API tests for RFP response generation (Parte 2)."""
from __future__ import annotations

import io
import os
import uuid

import pytest
from pypdf import PdfWriter
from sqlmodel import Session

from app.database import init_db
from app.domains.rfp.models import RfpHandoff, RfpTicket
from app.domains.rfp.service import get_db_engine as _orig_engine


def _make_pdf_bytes(text: str = "Sample RFP content") -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def rfp_gen_env(monkeypatch, sqlite_engine):
    monkeypatch.setenv("RFP_GENERATION_URL", "https://example.com/v1/chat/completions")
    monkeypatch.setenv("RFP_GENERATION_MODEL", "test-model")
    monkeypatch.setenv("RFP_GENERATION_API_KEY", "test-key")
    monkeypatch.setenv("RFP_MAX_ITERATIONS", "1")
    # Make background processing use the isolated SQLite engine.
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    import data.process.rfp_generation as gen

    def fake_generate_section(department_id, metadata, aspects, settings, feedback=None, client=None):
        return "Esta es una seccion de marketing. " * 20 + "Calidad consistente, experiencia calida y velocidad de servicio. Validez de la oferta: 30 dias desde su emision. Precio: 1000 COP y 1 USD. Términos de marca."

    monkeypatch.setattr(gen, "generate_section", fake_generate_section)


def test_generate_unknown_ticket_404(client, auth_headers):
    res = client.post(f"/rfp-requests/{uuid.uuid4()}/generate", headers=auth_headers)
    assert res.status_code == 404


def test_generate_from_completed_ticket_and_result(client, auth_headers, sqlite_engine):
    init_db(bind_engine=sqlite_engine)
    ticket_id = uuid.uuid4()
    with Session(sqlite_engine) as session:
        ticket = RfpTicket(
            id=ticket_id,
            status="analisis_completo",
            original_filename="sample.pdf",
            storage_path="/tmp/sample.pdf",
            idempotency_key=str(uuid.uuid4()),
        )
        session.add(ticket)
        session.commit()
    with Session(sqlite_engine) as session:
        handoff = RfpHandoff(
            ticket_id=ticket_id,
            key_aspects=[{"department": "marketing", "aspect": "Términos", "detail": "d"}],
            workstreams=[{"department": "marketing", "status": "pendiente"}],
        )
        session.add(handoff)
        session.commit()

    res = client.post(f"/rfp-requests/{ticket_id}/generate", headers=auth_headers)
    assert res.status_code == 202

    import time
    for _ in range(20):
        result = client.get(f"/rfp-requests/{ticket_id}/result", headers=auth_headers).json()
        if result.get("generation_handoff") is not None:
            break
        time.sleep(0.1)

    result = client.get(f"/rfp-requests/{ticket_id}/result", headers=auth_headers).json()
    assert result["generation_handoff"] is not None
    assert len(result["drafts"]) == 1
    assert result["drafts"][0]["department_id"] == "marketing"
    assert result["evaluations"][0]["overall_pass"] is True
    assert result["status"] in ("en_evaluación", "needs_human_review")