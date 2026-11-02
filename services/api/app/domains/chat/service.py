from __future__ import annotations

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
    user_id = str(user.get("uuid"))
    if not user_id:
        raise ValueError("usuario sin uuid")
    return create_session(user_id, location_id)


def get_chat_session(session_id: str) -> dict[str, Any] | None:
    return get_session(session_id)


def validate_chat_session(session: dict[str, Any], user: dict) -> bool:
    if session is None:
        return False
    if session.get("status") == "closed":
        return False
    if str(session.get("user_id")) != str(user.get("uuid")):
        return False
    if session.get("location_id") not in VALID_LOCATION_IDS:
        return False
    # Admin may view any; non-admin already matched user_id.
    return True


def append_chat_message(**kwargs: Any) -> dict[str, Any]:
    return append_message(**kwargs)


def get_chat_messages(session_id: str) -> list[dict[str, Any]]:
    return get_messages(session_id)


def update_chat_message(**kwargs: Any) -> None:
    update_message(**kwargs)