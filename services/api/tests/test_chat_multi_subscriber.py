import asyncio

from app.domains.chat import router as chat_router


def test_two_subscribers_one_generation(client, auth_headers, monkeypatch):
    res = client.post("/chat/sessions", headers=auth_headers, json={"location_id": "COL-01"})
    session_id = res.json()["session_id"]
    token = auth_headers["Authorization"].split(" ", 1)[1]

    calls = {"n": 0}

    async def fake_stream(question, **kwargs):
        calls["n"] += 1
        on_token = kwargs.get("on_token")
        if on_token is not None:
            await on_token("hola", 1, False)
        return {"run_id": "r", "thread_id": session_id, "conversation_id": session_id, "answer": "hola", "route": "grounded", "memory_proposal": None}

    monkeypatch.setattr(chat_router, "stream_agent_query", fake_stream)

    with client.websocket_connect(f"/chat/ws?session_id={session_id}&token={token}") as ws1:
        with client.websocket_connect(f"/chat/ws?session_id={session_id}&token={token}") as ws2:
            ws1.receive_json()  # snapshot
            ws2.receive_json()  # snapshot
            ws1.send_json({"event": "user_message", "data": {"text": "hi"}})
            # collect a token chunk on both
            seen1 = [ws1.receive_json() for _ in range(3)]
            seen2 = [ws2.receive_json() for _ in range(3)]
            assert any(e["event"] == "token_chunk" for e in seen1)
            assert any(e["event"] == "token_chunk" for e in seen2)
            assert calls["n"] == 1
