from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.database import db

sessions_table = db.table("chat_sessions")
messages_table = db.table("chat_messages")


def set_chat_tables(*, sessions=None, messages=None) -> None:
    global sessions_table, messages_table
    if sessions is not None:
        sessions_table = sessions
    if messages is not None:
        messages_table = messages


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_session(user_id: str, location_id: str) -> dict[str, Any]:
    session_id = f"chat-{uuid.uuid4().hex[:12]}"
    record = {
        "session_id": session_id,
        "agent_id": "manager_support",
        "user_id": user_id,
        "location_id": location_id,
        "status": "active",
        "created_at": _now(),
    }
    sessions_table.insert(record)
    return dict(record)


def get_session(session_id: str) -> dict[str, Any] | None:
    for row in sessions_table.all():
        if row.get("session_id") == session_id:
            return dict(row)
    return None


def update_session_status(session_id: str, status: str) -> None:
    sessions_table.update({"status": status}, lambda r: r.get("session_id") == session_id)


def append_message(
    *,
    session_id: str,
    message_id: str,
    role: str,
    content: str = "",
    generation_id: str | None = None,
    status: str = "complete",
    is_complete: bool = True,
    sequence: int = 0,
) -> dict[str, Any]:
    record = {
        "message_id": message_id,
        "session_id": session_id,
        "generation_id": generation_id,
        "role": role,
        "content": content,
        "status": status,
        "is_complete": is_complete,
        "sequence": sequence,
        "created_at": _now(),
        "completed_at": _now() if is_complete else None,
    }
    messages_table.insert(record)
    return dict(record)


def get_messages(session_id: str) -> list[dict[str, Any]]:
    rows = [dict(r) for r in messages_table.all() if r.get("session_id") == session_id]
    rows.sort(key=lambda r: r.get("created_at", ""))
    return rows


def update_message(
    message_id: str,
    *,
    content: str | None = None,
    status: str | None = None,
    is_complete: bool | None = None,
    completed_at: str | None = None,
) -> None:
    def _match(r):
        return r.get("message_id") == message_id

    patch: dict[str, Any] = {}
    if content is not None:
        patch["content"] = content
    if status is not None:
        patch["status"] = status
    if is_complete is not None:
        patch["is_complete"] = is_complete
    if completed_at is not None:
        patch["completed_at"] = completed_at
    if patch:
        messages_table.update(patch, _match)