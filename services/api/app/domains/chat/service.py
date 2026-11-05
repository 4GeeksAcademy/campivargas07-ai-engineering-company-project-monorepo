from __future__ import annotations

import os

from typing import Any

from app.domains.analytics.incidents.analysis import VALID_LOCATION_IDS

from .repository import (
    append_message,
    create_session,
    get_messages,
    get_session,
    update_message,
    update_session_status,
)


def validate_location_id(location_id: str) -> bool:
    return location_id in VALID_LOCATION_IDS


def create_chat_session(user: dict, location_id: str) -> dict[str, Any]:
    if not validate_location_id(location_id):
        raise ValueError("location_id inválido")
    if not user_can_access_location(user, location_id):
        raise ValueError("sin permisos para la location")
    user_id = str(user.get("uuid"))
    if not user_id:
        raise ValueError("usuario sin uuid")
    return create_session(user_id, location_id)


def get_chat_session(session_id: str) -> dict[str, Any] | None:
    return get_session(session_id)



def get_chat_checkpointer():
    """Return a durable LangGraph checkpointer if configured, else None (in-memory)."""
    url = os.getenv("CHAT_CHECKPOINT_DB_URL", "").strip()
    if not url:
        return None
    if url.startswith("sqlite"):
        from langgraph.checkpoint.sqlite import SqliteSaver

        path = url.replace("sqlite:///", "").replace("sqlite://", "")
        if not path:
            path = "chat_checkpoints.sqlite"
        return SqliteSaver.from_conn_string(path)
    if url.startswith("postgres"):
        from langgraph.checkpoint.postgres import PostgresSaver

        return PostgresSaver.from_conn_string(url)
    return None


def user_can_access_location(user: dict, location_id: str) -> bool:
    if str(user.get("role", "")).lower() == "admin":
        return True
    allowed = user.get("allowed_locations")
    if isinstance(allowed, list):
        return location_id in allowed
    # Backward-compatible default until a real location allowlist exists.
    return True


def validate_chat_session(session: dict[str, Any], user: dict) -> bool:
    if session is None:
        return False
    if session.get("status") == "closed":
        return False
    if str(session.get("user_id")) != str(user.get("uuid")):
        return False
    if session.get("location_id") not in VALID_LOCATION_IDS:
        return False
    if not user_can_access_location(user, session.get("location_id")):
        return False
    return True


def append_chat_message(**kwargs: Any) -> dict[str, Any]:
    return append_message(**kwargs)


def get_chat_messages(session_id: str) -> list[dict[str, Any]]:
    return get_messages(session_id)


def update_chat_message(**kwargs: Any) -> None:
    update_message(**kwargs)