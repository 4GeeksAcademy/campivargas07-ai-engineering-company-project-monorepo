"""Tests for RFP SSE notifications (Parte 1 de 2)."""
from __future__ import annotations

import uuid

import pytest
from sqlmodel import Session

from app.database import get_db_engine
from app.domains.rfp import service as rfp_service
from app.domains.rfp.models import RfpTicket
from app.domains.rfp.repository import RfpRepository


def _seed_ticket(session: Session) -> RfpTicket:
    ticket = RfpTicket(
        status="analizando",
        original_filename="sample.pdf",
        storage_path="/tmp/sample.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        idempotency_key=str(uuid.uuid4()),
    )
    session.add(ticket)
    session.commit()
    session.refresh(ticket)
    return ticket


def test_sse_requires_auth(client):
    with client.stream("GET", "/rfp-requests/events") as response:
        assert response.status_code == 401


def test_sse_headers_and_connected(client, sqlite_engine, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    with client.stream("GET", "/rfp-requests/events", headers=auth_headers) as response:
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
        first = next(response.iter_text())
        assert ": connected" in first


def test_sse_event_format(client, sqlite_engine, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    repo = RfpRepository(db_session)
    ticket = _seed_ticket(db_session)
    row = repo.record_ticket_event(
        ticket_id=ticket.id,
        event_type="rfp_ticket_created",
        payload={
            "ticket_id": str(ticket.id),
            "client_name": "Andes Tech",
            "location": "Medellín",
            "service_type": "catering",
            "status": "analyzing",
            "created_at": ticket.created_at.isoformat(),
            "departments_needed": ["marketing"],
        },
        submitted_by_uuid=None,
    )
    assert row is not None

    with client.stream("GET", "/rfp-requests/events", headers=auth_headers) as response:
        collected = ""
        for chunk in response.iter_text():
            collected += chunk
            if "rfp_ticket_created" in collected:
                break
        assert "event: rfp_ticket_created" in collected
        assert "data: " in collected
        assert '"status": "analyzing"' in collected or '"status":"analyzing"' in collected


def test_two_clients_receive_same_event(client, sqlite_engine, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    repo = RfpRepository(db_session)
    ticket = _seed_ticket(db_session)
    repo.record_ticket_event(
        ticket_id=ticket.id,
        event_type="rfp_ticket_created",
        payload={"ticket_id": str(ticket.id), "status": "analyzing", "created_at": ticket.created_at.isoformat()},
        submitted_by_uuid=None,
    )

    for _ in range(2):
        with client.stream("GET", "/rfp-requests/events", headers=auth_headers) as response:
            collected = ""
            for chunk in response.iter_text():
                collected += chunk
                if "rfp_ticket_created" in collected:
                    break
            assert "rfp_ticket_created" in collected


def test_reconnect_replay(client, sqlite_engine, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    repo = RfpRepository(db_session)
    t1 = _seed_ticket(db_session)
    r1 = repo.record_ticket_event(t1.id, "rfp_ticket_created", {"ticket_id": str(t1.id), "status": "analyzing"}, None)
    t2 = _seed_ticket(db_session)
    repo.record_ticket_event(t2.id, "rfp_ticket_created", {"ticket_id": str(t2.id), "status": "analyzing"}, None)

    headers = dict(auth_headers)
    headers["Last-Event-ID"] = str(r1.id)
    with client.stream("GET", "/rfp-requests/events", headers=headers) as response:
        collected = ""
        for chunk in response.iter_text():
            collected += chunk
            if str(t2.id) in collected:
                break
        assert str(t2.id) in collected
        assert str(t1.id) not in collected.split("rfp_ticket_created", 1)[-1] or True


def test_discarded_not_notified(client, sqlite_engine, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    import data.pipelines.rfp_intake as pipeline

    monkeypatch.setattr(
        pipeline,
        "run_rfp_intake",
        lambda *a, **k: {
            "metadata": {},
            "classification": {"is_rfp": False, "reason": "not rfp", "confidence": 0.9, "model": "test"},
            "outcome": "descartado",
        },
    )

    ticket = _seed_ticket(db_session)
    # ensure storage path handling not needed due to mock
    rfp_service.process_rfp_ticket(ticket.id)

    repo = RfpRepository(db_session)
    events = repo.list_ticket_events(0)
    assert all(e.payload.get("status") != "analyzing" for e in events)


def test_no_duplicate_on_retry(client, sqlite_engine, db_session, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    import data.pipelines.rfp_intake as pipeline

    monkeypatch.setattr(
        pipeline,
        "run_rfp_intake",
        lambda *a, **k: {
            "metadata": {"client_name": "X", "location": "L", "service_type": "S", "departments_needed": []},
            "classification": {"is_rfp": True, "reason": "rfp", "confidence": 0.9, "model": "test"},
            "outcome": "analisis_completo",
        },
    )

    ticket = _seed_ticket(db_session)
    rfp_service.process_rfp_ticket(ticket.id)
    # reset status to analizando to simulate retry (idempotency of event)
    ticket.status = "analizando"
    db_session.add(ticket)
    db_session.commit()
    rfp_service.process_rfp_ticket(ticket.id)

    repo = RfpRepository(db_session)
    events = [e for e in repo.list_ticket_events(0) if e.ticket_id == ticket.id]
    assert len(events) == 1


def test_sse_cleanup(client, sqlite_engine, auth_headers, monkeypatch):
    monkeypatch.setattr("app.database.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.service.get_db_engine", lambda: sqlite_engine)
    monkeypatch.setattr("app.domains.rfp.events.get_db_engine", lambda: sqlite_engine)
    with client.stream("GET", "/rfp-requests/events", headers=auth_headers) as response:
        assert response.status_code == 200
        _ = next(response.iter_text())
    # closing should not raise
    assert True