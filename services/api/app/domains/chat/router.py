from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, ConfigDict, Field

from app.domains.agent.streaming import stream_agent_query
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.service import decode_access_token
from app.domains.chat.pubsub import get_session_channel
from app.domains.chat.service import (
    append_chat_message,
    create_chat_session,
    get_chat_messages,
    get_chat_session,
    validate_chat_session,
    update_chat_message,
    update_session_status,
)

router = APIRouter(prefix="/chat", tags=["chat"])


class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    location_id: str = Field(min_length=1, max_length=32)


@router.post("/sessions")
def create_session(body: CreateSessionRequest, current_user: dict = Depends(get_current_user)):
    try:
        session = create_chat_session(current_user, body.location_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return session


@router.get("/sessions/{session_id}")
def get_session(session_id: str, current_user: dict = Depends(get_current_user)):
    session = get_chat_session(session_id)
    if session is None or not validate_chat_session(session, current_user):
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    messages = get_chat_messages(session_id)
    return {"session": session, "messages": messages}


async def _authenticate_websocket(websocket: WebSocket) -> tuple[dict[str, Any] | None, str | None]:
    # Query string auth
    token = websocket.query_params.get("token")
    session_id = websocket.query_params.get("session_id")
    if token:
        user = _user_from_token(token)
        if user is not None:
            return user, session_id
    # First-frame auth with timeout
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
        frame = json.loads(raw)
        if frame.get("event") == "auth":
            token = (frame.get("data") or {}).get("token")
            session_id = session_id or (frame.get("data") or {}).get("session_id")
            user = _user_from_token(token or "")
            if user is not None:
                await websocket.send_json({"event": "auth_ok", "data": {}})
                return user, session_id
    except Exception:
        pass
    return None, session_id


def _user_from_token(token: str) -> dict[str, Any] | None:
    payload = decode_access_token(token)
    if payload is None:
        return None
    # Reuse get_current_user logic by looking up users_table.
    from app.database import users_table

    user_id = payload.get("sub")
    try:
        user_doc = users_table.get(doc_id=int(user_id))
    except (ValueError, TypeError):
        return None
    if user_doc is None or not user_doc.get("is_active", False):
        return None
    if "uuid" not in user_doc:
        import uuid

        stable = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"brasaland-user-{user_doc.doc_id}"))
        users_table.update({"uuid": stable}, doc_ids=[user_doc.doc_id])
        user_doc["uuid"] = stable
    return user_doc


@router.websocket("/ws")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    user, session_id = await _authenticate_websocket(websocket)
    if user is None:
        await websocket.send_json({"event": "error", "data": {"code": "unauthorized", "message": "Autenticación requerida"}})
        await websocket.close(code=4401)
        return
    if not session_id:
        await websocket.send_json({"event": "error", "data": {"code": "missing_session", "message": "session_id requerido"}})
        await websocket.close(code=4400)
        return

    session = get_chat_session(session_id)
    if session is None or not validate_chat_session(session, user):
        await websocket.send_json({"event": "error", "data": {"code": "forbidden", "message": "Sesión no encontrada o ajena"}})
        await websocket.close(code=4403)
        return

    channel = get_session_channel(session_id)
    subscriber = await channel.subscribe()
    # Send snapshot first.
    messages = get_chat_messages(session_id)
    await websocket.send_json({
        "event": "session_snapshot",
        "data": {"session_id": session_id, "status": session.get("status"), "messages": messages, "active_generation": channel.active_generation},
    })

    receive_task = asyncio.create_task(_receive_loop(websocket, session_id, user, channel))
    send_task = asyncio.create_task(_send_loop(websocket, subscriber, session_id))

    done, pending = await asyncio.wait({receive_task, send_task}, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in done:
        try:
            task.result()
        except Exception:
            pass
    await channel.unsubscribe(subscriber)


async def _receive_loop(websocket: WebSocket, session_id: str, user: dict, channel) -> None:
    while True:
        text = await websocket.receive_text()
        try:
            frame = json.loads(text)
        except json.JSONDecodeError:
            await channel.publish({"event": "error", "data": {"session_id": session_id, "code": "invalid_frame", "message": "Frame inválido"}})
            continue
        event = frame.get("event")
        data = frame.get("data") or {}
        if event == "user_message":
            await _handle_user_message(session_id, user, channel, data)
        elif event == "interrupt_requested":
            await _handle_interrupt(session_id, user, channel, data)
        else:
            await channel.publish({"event": "error", "data": {"session_id": session_id, "code": "unknown_event", "message": "Evento no soportado"}})


async def _handle_user_message(session_id: str, user: dict, channel, data: dict) -> None:
    text = str(data.get("text", "")).strip()
    if not text:
        await channel.publish({"event": "error", "data": {"session_id": session_id, "code": "empty_message", "message": "Mensaje vacío"}})
        return
    # If a generation is active, treat as implicit interrupt with new_input.
    if channel.active_generation is not None:
        await _handle_interrupt(session_id, user, channel, {"generation_id": channel.active_generation, "new_input": text})
        return
    from uuid import uuid4

    message_id = f"msg-{uuid4().hex[:12]}"
    generation_id = f"gen-{uuid4().hex[:12]}"
    append_chat_message(session_id=session_id, message_id=message_id, role="user", content=text, status="complete", is_complete=True)

    await channel.publish({"event": "user_message", "data": {"session_id": session_id, "message_id": message_id, "text": text}})

    # Start generation task.
    channel.active_generation = generation_id
    assistant_message_id = f"msg-{uuid4().hex[:12]}"
    append_chat_message(session_id=session_id, message_id=assistant_message_id, role="assistant", content="", status="streaming", is_complete=False, generation_id=generation_id)

    async def _run_generation():
        accumulated: list[str] = []
        seq = 0
        cancelled = False
        try:
            async def on_token(token: str, sequence: int, deterministic: bool):
                nonlocal seq
                seq = sequence
                accumulated.append(token)
                await channel.publish({
                    "event": "token_chunk",
                    "data": {
                        "session_id": session_id,
                        "message_id": assistant_message_id,
                        "generation_id": generation_id,
                        "token": token,
                        "sequence": sequence,
                    },
                })

            result = await stream_agent_query(
                text,
                thread_id=session_id,
                conversation_id=session_id,
                user_uuid=user.get("uuid"),
                on_token=on_token,
            )
            answer = result.get("answer", "")
            # Ensure full content persisted.
            from datetime import datetime, timezone as _tz
            update_chat_message(message_id=assistant_message_id, content=answer, status="complete", is_complete=True, completed_at=datetime.now(_tz.utc).isoformat())
            channel.active_generation = None
            await channel.publish({
                "event": "generation_completed",
                "data": {
                    "session_id": session_id,
                    "message_id": assistant_message_id,
                    "generation_id": generation_id,
                    "route": result.get("route"),
                    "memory_proposal": result.get("memory_proposal"),
                },
            })
        except asyncio.CancelledError:
            cancelled = True
            partial = "".join(accumulated)
            update_chat_message(message_id=assistant_message_id, content=partial, status="interrupted", is_complete=False)
            channel.active_generation = None
            await channel.publish({
                "event": "generation_interrupted",
                "data": {
                    "session_id": session_id,
                    "message_id": assistant_message_id,
                    "generation_id": generation_id,
                    "status": "interrupted",
                },
            })
            raise
        except Exception as exc:
            channel.active_generation = None
            update_chat_message(message_id=assistant_message_id, content="".join(accumulated), status="complete", is_complete=True)
            await channel.publish({"event": "error", "data": {"session_id": session_id, "code": "generation_failed", "message": str(exc)}})

    task = asyncio.create_task(_run_generation())
    channel.generation_task = task


async def _handle_interrupt(session_id: str, user: dict, channel, data: dict) -> None:
    generation_id = data.get("generation_id") or channel.active_generation
    new_input = str(data.get("new_input", "")).strip()
    if channel.active_generation is None or generation_id != channel.active_generation:
        return
    if channel.generation_task is not None and not channel.generation_task.done():
        channel.generation_task.cancel()
        try:
            await channel.generation_task
        except (asyncio.CancelledError, Exception):
            pass
    channel.generation_task = None
    if new_input:
        await _handle_user_message(session_id, user, channel, {"text": new_input})


async def _send_loop(websocket: WebSocket, subscriber, session_id: str) -> None:
    while True:
        event = await subscriber.get()
        await websocket.send_json(event)