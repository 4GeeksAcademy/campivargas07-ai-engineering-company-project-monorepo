"""Server-Sent Events stream for RFP ticket arrivals (Parte 1 de 2)."""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from fastapi import Request
from sqlmodel import Session

from app.database import get_db_engine
from app.domains.auth.service import decode_access_token
from app.domains.rfp.repository import RfpRepository


def can_view_rfp_event(user: dict, event) -> bool:
    """Authorization: a client receives only the tickets it can consult."""
    if str(user.get("role", "")).lower() == "admin":
        return True
    if event.submitted_by_uuid is None:
        return True
    return str(event.submitted_by_uuid) == str(user.get("uuid"))


def format_sse(event) -> str:
    lines: list[str] = []
    if event.id is not None:
        lines.append(f"id: {event.id}")
    lines.append("event: rfp_ticket_created")
    lines.append("data: " + json.dumps(event.payload, ensure_ascii=False))
    lines.append("")
    return "\n".join(lines) + "\n"


async def rfp_ticket_event_stream(
    request: Request,
    current_user: dict,
    last_event_id: Optional[str] = None,
):
    """Async generator yielding SSE frames for new RFP tickets."""
    yield ": connected\n\n"

    try:
        last_id = int(last_event_id) if last_event_id not in (None, "") else 0
    except (TypeError, ValueError):
        last_id = 0

    last_heartbeat = time.monotonic()

    while True:
        if await request.is_disconnected():
            break

        # Token expiry handling for long-lived connections.
        auth_header = request.headers.get("authorization", "")
        token_str = None
        if auth_header.lower().startswith("bearer "):
            token_str = auth_header.split(" ", 1)[1].strip()
        if token_str:
            payload = decode_access_token(token_str)
            if payload is None:
                yield "event: error\ndata: {\"detail\":\"invalid_token\"}\n\n"
                break
            exp = payload.get("exp")
            if exp is not None and time.time() >= float(exp):
                yield "event: error\ndata: {\"detail\":\"token_expired\"}\n\n"
                break

        rows = []
        try:
            engine = get_db_engine()
            with Session(engine) as session:
                repo = RfpRepository(session)
                rows = repo.list_ticket_events(after_id=last_id, limit=100)
        except Exception:
            rows = []

        delivered = False
        for row in rows:
            if row.id is not None:
                last_id = row.id
            if not can_view_rfp_event(current_user, row):
                continue
            yield format_sse(row)
            delivered = True

        now = time.monotonic()
        if (not delivered) and (now - last_heartbeat >= 15):
            yield ": keep-alive\n\n"
            last_heartbeat = now
        elif delivered:
            last_heartbeat = now

        await asyncio.sleep(1)