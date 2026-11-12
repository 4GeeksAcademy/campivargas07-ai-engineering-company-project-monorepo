"""Human-confirmation gate for irreversible supplier actions.

Stores short-lived, single-use confirmation tokens bound to a concrete action,
its parameters and the requesting actor. Backend validation prevents reuse,
parameter tampering and expiry bypass.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from tinydb import Query

from app.database import suppliers_table

_Q = Query()

# Patchable handle (tests inject an isolated table).
confirmations_table = None


def _table():
    global confirmations_table
    if confirmations_table is None:
        from app.database import db

        confirmations_table = db.table("supplier_confirmations")
    return confirmations_table


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _params_hash(params: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()


def create_confirmation(
    supplier_id: str,
    action: str,
    params: dict[str, Any],
    actor_uuid: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    table = _table()
    confirmation_id = uuid.uuid4().hex
    now = _now()
    expires = now + timedelta(seconds=ttl_seconds)
    record = {
        "confirmation_id": confirmation_id,
        "supplier_id": supplier_id,
        "action": action,
        "params_hash": _params_hash(params),
        "actor_uuid": actor_uuid,
        "created_at": now.isoformat(),
        "expires_at": expires.isoformat(),
        "used": False,
        "used_at": None,
    }
    table.insert(record)
    return {"confirmation_id": confirmation_id, "expires_at": expires.isoformat()}


def validate_and_consume(
    confirmation_id: str,
    supplier_id: str,
    action: str,
    params: dict[str, Any],
    actor_uuid: str,
) -> bool:
    table = _table()
    rec = table.get(_Q.confirmation_id == confirmation_id)
    if rec is None:
        return False
    if rec.get("used"):
        return False
    try:
        expires = datetime.fromisoformat(rec["expires_at"])
    except (TypeError, ValueError):
        return False
    if expires <= _now():
        return False
    if rec.get("supplier_id") != supplier_id:
        return False
    if rec.get("action") != action:
        return False
    if rec.get("params_hash") != _params_hash(params):
        return False
    if rec.get("actor_uuid") != actor_uuid:
        return False
    table.update(
        {"used": True, "used_at": _now().isoformat()},
        _Q.confirmation_id == confirmation_id,
    )
    return True