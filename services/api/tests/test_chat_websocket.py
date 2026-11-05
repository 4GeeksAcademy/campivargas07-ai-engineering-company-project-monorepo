import asyncio
from unittest.mock import AsyncMock

import pytest

from app.domains.chat import router as chat_router


def test_chat_session_create_and_auth_required(client):
    assert client.post("/chat/sessions", json={"location_id": "COL-01"}).status_code in (401, 403)


def test_chat_session_create(client, auth_headers):
    res = client.post("/chat/sessions", headers=auth_headers, json={"location_id": "COL-01"})
    assert res.status_code == 200
    data = res.json()
    assert data["agent_id"] == "manager_support"
    assert data["location_id"] == "COL-01"
    assert data["status"] == "active"


def test_chat_websocket_auth_timeout(client):
    with client.websocket_connect("/chat/ws?session_id=missing") as ws:
        msg = ws.receive_json()
        assert msg["event"] == "error"


def test_chat_websocket_snapshot_and_message(client, auth_headers, monkeypatch):
    # create session
    res = client.post("/chat/sessions", headers=auth_headers, json={"location_id": "COL-01"})
    session_id = res.json()["session_id"]
    token = auth_headers["Authorization"].split(" ", 1)[1]

    async def fake_stream(question, **kwargs):
        on_token = kwargs.get("on_token")
        if on_token is not None:
            await on_token("Hola", 1, False)
            await on_token(" mundo", 2, False)
        return {"run_id": "r", "thread_id": session_id, "conversation_id": session_id, "answer": "Hola mundo", "route": "grounded", "memory_proposal": None}

    monkeypatch.setattr(chat_router, "stream_agent_query", fake_stream)

    with client.websocket_connect(f"/chat/ws?session_id={session_id}&token={token}") as ws:
        snapshot = ws.receive_json()
        assert snapshot["event"] == "session_snapshot"
        ws.send_json({"event": "user_message", "data": {"text": "hola"}})
        events = []
        for _ in range(4):
            events.append(ws.receive_json())
        types = [e["event"] for e in events]
        assert "user_message" in types
        assert "token_chunk" in types
        assert "generation_completed" in types


def test_chat_websocket_interrupt(client, auth_headers, monkeypatch):
    res = client.post("/chat/sessions", headers=auth_headers, json={"location_id": "COL-01"})
    session_id = res.json()["session_id"]
    token = auth_headers["Authorization"].split(" ", 1)[1]

    async def slow_stream(question, **kwargs):
        on_token = kwargs.get("on_token")
        if on_token is not None:
            await on_token("parcial", 1, False)
        await asyncio.sleep(10)
        if on_token is not None:
            await on_token(" tarde", 2, False)
        return {"run_id": "r", "thread_id": session_id, "conversation_id": session_id, "answer": "parcial tarde", "route": "grounded", "memory_proposal": None}

    monkeypatch.setattr(chat_router, "stream_agent_query", slow_stream)

    with client.websocket_connect(f"/chat/ws?session_id={session_id}&token={token}") as ws:
        ws.receive_json()  # snapshot
        ws.send_json({"event": "user_message", "data": {"text": "hola"}})
        first = ws.receive_json()  # user_message
        assert first["event"] == "user_message"
        chunk = ws.receive_json()  # token_chunk
        assert chunk["event"] == "token_chunk"
        ws.send_json({"event": "interrupt_requested", "data": {"generation_id": chunk["data"]["generation_id"], "new_input": "corrige"}})
        # collect until interrupted or completed
        seen = []
        for _ in range(5):
            try:
                seen.append(ws.receive_json())
            except Exception:
                break
        assert any(e["event"] == "generation_interrupted" for e in seen)