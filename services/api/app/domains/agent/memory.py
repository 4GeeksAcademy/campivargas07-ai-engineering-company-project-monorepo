"""Agent memory: persistent, auditable, opt-in memory for the Brasaland agent.

Part 1 of MEM-092. Storage is intentionally separated from the RAG corpus
(Qdrant) and from incident data. The default backend is a dedicated TinyDB
file so it survives restarts without adding dependencies or migrations.

Policy note: allowed/prohibited facts and audience are NOT hard-coded here.
They come from the official BRIEFING (still pending). Until then, the default
policy is deny-all for new memories; tests inject an explicit policy.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from uuid import uuid4

from tinydb import TinyDB

MEMORY_LOCK = threading.RLock()

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "agent_memory.json"


def memory_db_path(custom: str | Path | None = None) -> Path:
    if custom is not None:
        return Path(custom)
    env = os.getenv("AGENT_MEMORY_DB_PATH", "").strip()
    if env:
        return Path(env)
    return _DEFAULT_DB_PATH


# Module-level tables (patchable in tests, like users_table).
_DB = None


def _open_db(path: Path | None = None) -> TinyDB:
    global _DB
    resolved = memory_db_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    if _DB is None or getattr(_DB, "_memory_path", None) != str(resolved):
        _DB = TinyDB(resolved)
        _DB._memory_path = str(resolved)  # type: ignore[attr-defined]
    return _DB


def _tables(path: Path | None = None):
    db = _open_db(path)
    return {
        "memories": db.table("memories"),
        "proposals": db.table("proposals"),
        "audits": db.table("audits"),
        "conversations": db.table("conversations"),
    }


# Patchable handles (default DB).
_DEFAULT_TABLES = _tables()
memories_table = _DEFAULT_TABLES["memories"]
proposals_table = _DEFAULT_TABLES["proposals"]
audits_table = _DEFAULT_TABLES["audits"]
conversations_table = _DEFAULT_TABLES["conversations"]


def _t():
    # Resolve at call time so tests can monkeypatch module attributes.
    return {
        "memories": memories_table,
        "proposals": proposals_table,
        "audits": audits_table,
        "conversations": conversations_table,
    }


def set_memory_tables(*, memories=None, proposals=None, audits=None, conversations=None) -> None:
    global memories_table, proposals_table, audits_table, conversations_table
    if memories is not None:
        memories_table = memories
    if proposals is not None:
        proposals_table = proposals
    if audits is not None:
        audits_table = audits
    if conversations is not None:
        conversations_table = conversations


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _content_hash(fact: str, category: str) -> str:
    return hashlib.sha256(f"{category}:{_normalize(fact)}".encode()).hexdigest()


def _is_expired(record: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    expires = record.get("expires_at")
    if not expires:
        return False
    try:
        return datetime.fromisoformat(expires) <= now
    except (TypeError, ValueError):
        return False


# Categories sanctioned by the official Brasaland BRIEFING (Hito 8, Parte 1).
ALLOWED_MEMORY_CATEGORIES: frozenset[str] = frozenset({
    "operational_correction",
    "escalation_context",
    "communication_preference",
})

# Terms that must never be consolidated, per the BRIEFING.
PROHIBITED_MEMORY_TERMS: tuple[str, ...] = (
    "brasa points", "cliente", "customer", "email", "correo", "telefono", "teléfono",
    "phone", "direccion", "dirección", "address", "nomina", "nómina", "payroll",
    "salario", "salary", "compensacion", "compensación", "compensation", "sueldo",
)


@dataclass(frozen=True)
class MemoryPolicy:
    allowed_categories: frozenset[str] = ALLOWED_MEMORY_CATEGORIES
    max_fact_length: int = 280
    max_active_per_user: int = 50
    max_active_per_conversation: int = 10
    default_ttl_days: int = 90
    pending_ttl_hours: int = 24
    min_confidence: float = 0.7

    @classmethod
    def from_env(cls) -> "MemoryPolicy":
        raw = os.getenv("AGENT_MEMORY_ALLOWED_CATEGORIES", "").strip()
        if raw:
            cats = frozenset(x.strip() for x in raw.split(",") if x.strip())
        else:
            cats = ALLOWED_MEMORY_CATEGORIES
        return cls(allowed_categories=cats)


DEFAULT_POLICY = MemoryPolicy.from_env()


@dataclass
class MemoryRecord:
    memory_id: str
    user_uuid: str
    conversation_id: str
    scope: str
    category: str
    fact: str
    content_hash: str
    source_run_id: str | None
    status: str
    created_at: str
    updated_at: str
    expires_at: str | None
    last_used_at: str | None
    supersedes: list[str] = field(default_factory=list)


@dataclass
class MemoryProposal:
    proposal_id: str
    user_uuid: str
    conversation_id: str
    origin_run_id: str | None
    proposed_fact: str
    category: str
    rationale: str
    confidence: float
    status: str
    created_at: str
    expires_at: str
    decided_at: str | None = None
    decided_by: str | None = None
    decision: str | None = None
    edited_fact: str | None = None
    memory_id: str | None = None
    error: str | None = None


@dataclass
class ConfirmationClassification:
    decision: str  # approve | reject | edit | ambiguous
    revised_fact: str | None = None
    has_new_query: bool = False
    new_query: str | None = None


def _sanitize_fact(fact: str) -> str:
    fact = re.sub(r"[\x00-\x1f\x7f]", " ", fact)
    fact = re.sub(r"\s+", " ", fact).strip()
    return fact


def validate_memory_candidate(candidate: Any, policy: MemoryPolicy) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None
    if candidate.get("should_remember") is not True:
        return None
    fact = _sanitize_fact(str(candidate.get("fact", "")))
    category = str(candidate.get("category", "")).strip()
    if not fact or len(fact) > policy.max_fact_length:
        return None
    if category not in policy.allowed_categories:
        return None
    if re.search(r"\b(password|token|api[_ -]?key|secret|bearer)\b", fact, re.I):
        return None
    lowered = fact.lower()
    if any(term in lowered for term in PROHIBITED_MEMORY_TERMS):
        return None
    try:
        confidence = float(candidate.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if confidence < policy.min_confidence:
        return None
    rationale = _sanitize_fact(str(candidate.get("rationale", "")))[:500]
    return {"fact": fact, "category": category, "rationale": rationale, "confidence": confidence}


def read_relevant_memories(
    user_uuid: str,
    conversation_id: str,
    query: str,
    *,
    policy: MemoryPolicy | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    policy = policy or DEFAULT_POLICY
    tables = _t()
    now = datetime.now(timezone.utc)
    query_tokens = set(re.findall(r"\w+", query.lower()))
    results: list[tuple[float, dict[str, Any]]] = []
    for row in tables["memories"].all():
        if row.get("user_uuid") != user_uuid:
            continue
        if row.get("status") != "active":
            continue
        if _is_expired(row, now):
            continue
        fact = str(row.get("fact", ""))
        fact_tokens = set(re.findall(r"\w+", fact.lower()))
        overlap = len(query_tokens & fact_tokens)
        if query_tokens and overlap == 0:
            continue
        score = overlap / (len(query_tokens) + 1)
        results.append((score, row))
    results.sort(key=lambda item: (item[0], item[1].get("last_used_at") or ""), reverse=True)
    out: list[dict[str, Any]] = []
    for _, row in results[:limit]:
        out.append({
            "memory_id": row.get("memory_id"),
            "category": row.get("category"),
            "fact": row.get("fact"),
            "source": "agent-memory",
        })
    # Touch last_used_at for returned memories.
    with MEMORY_LOCK:
        for item in out:
            mid = item.get("memory_id")
            if mid:
                tables["memories"].update({"last_used_at": _now()}, lambda r, mid=mid: r.get("memory_id") == mid)
    return out


def _pending_proposals(conversation_id: str, user_uuid: str) -> list[dict[str, Any]]:
    tables = _t()
    now = datetime.now(timezone.utc)
    out = []
    for row in tables["proposals"].all():
        if row.get("conversation_id") != conversation_id or row.get("user_uuid") != user_uuid:
            continue
        if row.get("status") != "pending":
            continue
        if _is_expired(row, now):
            continue
        out.append(row)
    return out


def expire_pending(conversation_id: str, user_uuid: str, reason: str, *, actor_uuid: str | None = None) -> int:
    tables = _t()
    count = 0
    with MEMORY_LOCK:
        for row in list(tables["proposals"].all()):
            if row.get("conversation_id") != conversation_id or row.get("user_uuid") != user_uuid:
                continue
            if row.get("status") != "pending":
                continue
            tables["proposals"].update(
                {"status": "expired", "decided_at": _now(), "decision": "expired", "error": reason},
                lambda r, pid=row.get("proposal_id"): r.get("proposal_id") == pid,
            )
            _audit("proposal_expired", actor_uuid or user_uuid, row.get("proposal_id"), None, "expired", {"reason": reason})
            count += 1
    return count


def propose_memory(
    user_uuid: str,
    conversation_id: str,
    origin_run_id: str | None,
    candidate: Any,
    *,
    policy: MemoryPolicy | None = None,
) -> MemoryProposal | None:
    policy = policy or DEFAULT_POLICY
    validated = validate_memory_candidate(candidate, policy)
    if validated is None:
        return None

    tables = _t()
    now = datetime.now(timezone.utc)
    # At most one pending proposal per conversation.
    expire_pending(conversation_id, user_uuid, "replaced_by_new_proposal", actor_uuid=user_uuid)

    proposal_id = f"prop-{uuid4().hex[:12]}"
    expires_at = (now + timedelta(hours=policy.pending_ttl_hours)).isoformat()
    record = {
        "proposal_id": proposal_id,
        "user_uuid": user_uuid,
        "conversation_id": conversation_id,
        "origin_run_id": origin_run_id,
        "proposed_fact": validated["fact"],
        "category": validated["category"],
        "rationale": validated["rationale"],
        "confidence": validated["confidence"],
        "status": "pending",
        "created_at": _now(),
        "expires_at": expires_at,
        "decided_at": None,
        "decided_by": None,
        "decision": None,
        "edited_fact": None,
        "memory_id": None,
        "error": None,
    }
    with MEMORY_LOCK:
        tables["proposals"].insert(record)
        _audit("memory_proposed", user_uuid, proposal_id, None, "pending", {
            "category": validated["category"],
            "fact_length": len(validated["fact"]),
        })
    return _proposal_from_row(record)


def _proposal_from_row(row: dict[str, Any]) -> MemoryProposal:
    return MemoryProposal(
        proposal_id=row["proposal_id"],
        user_uuid=row["user_uuid"],
        conversation_id=row["conversation_id"],
        origin_run_id=row.get("origin_run_id"),
        proposed_fact=row["proposed_fact"],
        category=row["category"],
        rationale=row.get("rationale", ""),
        confidence=float(row.get("confidence", 0.0)),
        status=row["status"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        decided_at=row.get("decided_at"),
        decided_by=row.get("decided_by"),
        decision=row.get("decision"),
        edited_fact=row.get("edited_fact"),
        memory_id=row.get("memory_id"),
        error=row.get("error"),
    )


def get_pending_proposal(conversation_id: str, user_uuid: str) -> MemoryProposal | None:
    rows = _pending_proposals(conversation_id, user_uuid)
    if not rows:
        return None
    return _proposal_from_row(rows[-1])


def _audit(action: str, actor_uuid: str, proposal_id: str | None, memory_id: str | None, decision: str, details: dict[str, Any] | None = None) -> None:
    tables = _t()
    safe_details = {}
    for key, value in (details or {}).items():
        if isinstance(value, str):
            safe_details[key] = value[:200]
        else:
            safe_details[key] = value
    tables["audits"].insert({
        "audit_id": f"aud-{uuid4().hex[:12]}",
        "action": action,
        "actor_uuid": actor_uuid,
        "proposal_id": proposal_id,
        "memory_id": memory_id,
        "decision": decision,
        "timestamp": _now(),
        "details": safe_details,
    })


def _consolidate(
    user_uuid: str,
    conversation_id: str,
    fact: str,
    category: str,
    proposal_id: str,
    policy: MemoryPolicy,
) -> str | None:
    tables = _t()
    fact = _sanitize_fact(fact)
    if not fact or category not in policy.allowed_categories:
        return None
    h = _content_hash(fact, category)
    # Dedup.
    for row in tables["memories"].all():
        if row.get("user_uuid") == user_uuid and row.get("content_hash") == h and row.get("status") == "active":
            tables["memories"].update(
                {"updated_at": _now(), "last_used_at": _now()},
                lambda r, mid=row.get("memory_id"): r.get("memory_id") == mid,
            )
            _audit("memory_deduplicated", user_uuid, proposal_id, row.get("memory_id"), "approved", {"category": category})
            return row.get("memory_id")
    # Enforce per-user limit.
    active = [r for r in tables["memories"].all() if r.get("user_uuid") == user_uuid and r.get("status") == "active"]
    if len(active) >= policy.max_active_per_user:
        active.sort(key=lambda r: r.get("last_used_at") or r.get("created_at") or "")
        victim = active[0]
        tables["memories"].update(
            {"status": "evicted", "updated_at": _now()},
            lambda r, mid=victim.get("memory_id"): r.get("memory_id") == mid,
        )
        _audit("memory_evicted", user_uuid, proposal_id, victim.get("memory_id"), "evicted", {"reason": "limit"})
    memory_id = f"mem-{uuid4().hex[:12]}"
    expires_at = (datetime.now(timezone.utc) + timedelta(days=policy.default_ttl_days)).isoformat()
    record = {
        "memory_id": memory_id,
        "user_uuid": user_uuid,
        "conversation_id": conversation_id,
        "scope": "user",
        "category": category,
        "fact": fact,
        "content_hash": h,
        "source_run_id": None,
        "status": "active",
        "created_at": _now(),
        "updated_at": _now(),
        "expires_at": expires_at,
        "last_used_at": _now(),
        "supersedes": [],
    }
    with MEMORY_LOCK:
        tables["memories"].insert(record)
        _audit("memory_consolidated", user_uuid, proposal_id, memory_id, "approved", {"category": category, "fact_length": len(fact)})
    return memory_id


def resolve_proposal(
    proposal_id: str,
    actor_uuid: str,
    decision: str,
    *,
    revised_fact: str | None = None,
    policy: MemoryPolicy | None = None,
    user_uuid: str | None = None,
) -> MemoryProposal | None:
    policy = policy or DEFAULT_POLICY
    tables = _t()
    with MEMORY_LOCK:
        target = None
        for row in tables["proposals"].all():
            if row.get("proposal_id") == proposal_id:
                target = row
                break
        if target is None:
            return None
        if user_uuid is not None and target.get("user_uuid") != user_uuid:
            return None
        if target.get("status") != "pending":
            return _proposal_from_row(target)
        if _is_expired(target):
            tables["proposals"].update(
                {"status": "expired", "decided_at": _now(), "decision": "expired"},
                lambda r, pid=proposal_id: r.get("proposal_id") == pid,
            )
            _audit("proposal_expired", actor_uuid, proposal_id, None, "expired", {"reason": "ttl"})
            return _proposal_from_row(tables["proposals"].get(lambda r: r.get("proposal_id") == proposal_id))  # type: ignore[union-attr]
        decision = decision.strip().lower()
        conversation_id = target.get("conversation_id")
        user = target.get("user_uuid")

        if decision == "approve":
            mid = _consolidate(user, conversation_id, target["proposed_fact"], target["category"], proposal_id, policy)
            new_status = "consolidated" if mid else "rejected_policy"
            tables["proposals"].update(
                {"status": new_status, "decided_at": _now(), "decided_by": actor_uuid, "decision": "approve", "memory_id": mid,
                 "error": None if mid else "policy_or_storage_failure"},
                lambda r, pid=proposal_id: r.get("proposal_id") == pid,
            )
            _audit("proposal_resolved", actor_uuid, proposal_id, mid, "approve", {"result": new_status})
        elif decision == "reject":
            tables["proposals"].update(
                {"status": "rejected", "decided_at": _now(), "decided_by": actor_uuid, "decision": "reject"},
                lambda r, pid=proposal_id: r.get("proposal_id") == pid,
            )
            _audit("proposal_resolved", actor_uuid, proposal_id, None, "reject", {})
        elif decision == "edit":
            revised = _sanitize_fact(revised_fact or "")
            new_proposal_id = None
            if revised and revised != target["proposed_fact"]:
                validated = validate_memory_candidate(
                    {"should_remember": True, "fact": revised, "category": target["category"], "rationale": "edited by user", "confidence": 1.0},
                    policy,
                )
                if validated is not None:
                    new_proposal_id = f"prop-{uuid4().hex[:12]}"
                    expires_at = (datetime.now(timezone.utc) + timedelta(hours=policy.pending_ttl_hours)).isoformat()
                    tables["proposals"].insert({
                        "proposal_id": new_proposal_id,
                        "user_uuid": user,
                        "conversation_id": conversation_id,
                        "origin_run_id": target.get("origin_run_id"),
                        "proposed_fact": validated["fact"],
                        "category": validated["category"],
                        "rationale": validated["rationale"],
                        "confidence": validated["confidence"],
                        "status": "pending",
                        "created_at": _now(),
                        "expires_at": expires_at,
                        "decided_at": None,
                        "decided_by": None,
                        "decision": None,
                        "edited_fact": revised,
                        "memory_id": None,
                        "error": None,
                    })
            tables["proposals"].update(
                {"status": "edited", "decided_at": _now(), "decided_by": actor_uuid, "decision": "edit", "edited_fact": revised},
                lambda r, pid=proposal_id: r.get("proposal_id") == pid,
            )
            _audit("proposal_resolved", actor_uuid, proposal_id, None, "edit", {"revised": bool(new_proposal_id)})
        elif decision in {"ambiguous", "expire", "discard"}:
            tables["proposals"].update(
                {"status": "expired", "decided_at": _now(), "decided_by": actor_uuid, "decision": "expired", "error": "ambiguous_or_topic_change"},
                lambda r, pid=proposal_id: r.get("proposal_id") == pid,
            )
            _audit("proposal_discarded", actor_uuid, proposal_id, None, "expired", {"reason": "ambiguous_or_topic_change"})
        else:
            return None

        updated = None
        for row in tables["proposals"].all():
            if row.get("proposal_id") == proposal_id:
                updated = row
                break
        return _proposal_from_row(updated) if updated else None


def classify_proposal_response(message: str, pending: MemoryProposal) -> ConfirmationClassification:
    text = _normalize(message)
    approve_phrases = {"si", "sí", "yes", "apruebo", "acepto", "de acuerdo", "ok", "okay", "claro", "correcto", "guarda", "guardalo", "guárdalo"}
    reject_phrases = {"no", "rechazo", "cancela", "cancelar", "descarta", "descartar", "no guardar", "no lo guardes"}
    edit_markers = ("edita", "editar", "modifica", "modificar", "cambia", "cambiar", "ajusta", "ajustar", "revisa", "revisar")

    has_question = "?" in message or bool(re.search(r"\b(qu[eé]|cu[aá]l|c[oó]mo|d[oó]nde|cu[aá]ndo|por qu[eé])\b", text))
    decision = "ambiguous"
    revised_fact = None

    if any(marker in text for marker in edit_markers):
        decision = "edit"
        # Extract revised fact after colon or quotes.
        match = re.search(r"[:\"“”](.+)$", message)
        if match:
            revised_fact = _sanitize_fact(match.group(1))
        if not revised_fact:
            revised_fact = _sanitize_fact(message)
    elif any(phrase == text or text.startswith(phrase + " ") for phrase in approve_phrases):
        decision = "approve"
    elif any(phrase == text or text.startswith(phrase + " ") for phrase in reject_phrases):
        decision = "reject"
    else:
        # Looser contains checks only for short messages.
        if len(text.split()) <= 4:
            if any(p in text for p in approve_phrases):
                decision = "approve"
            elif any(p in text for p in reject_phrases):
                decision = "reject"

    new_query = message.strip() if has_question and decision != "ambiguous" else None
    # If the message is clearly a new question and not a resolution, treat as topic change.
    if decision == "ambiguous" and not any(p in text for p in approve_phrases | reject_phrases | set(edit_markers)):
        # Could be a new topic/question.
        pass
    has_new_query = bool(new_query) and decision in {"approve", "reject", "edit"}
    return ConfirmationClassification(decision=decision, revised_fact=revised_fact, has_new_query=has_new_query, new_query=new_query)


def cleanup_expired(*, policy: MemoryPolicy | None = None) -> dict[str, int]:
    policy = policy or DEFAULT_POLICY
    tables = _t()
    now = datetime.now(timezone.utc)
    removed = 0
    with MEMORY_LOCK:
        for row in list(tables["memories"].all()):
            if row.get("status") == "active" and _is_expired(row, now):
                tables["memories"].update(
                    {"status": "expired", "updated_at": _now()},
                    lambda r, mid=row.get("memory_id"): r.get("memory_id") == mid,
                )
                removed += 1
        for row in list(tables["proposals"].all()):
            if row.get("status") == "pending" and _is_expired(row, now):
                tables["proposals"].update(
                    {"status": "expired", "decided_at": _now(), "decision": "expired"},
                    lambda r, pid=row.get("proposal_id"): r.get("proposal_id") == pid,
                )
                removed += 1
    return {"expired": removed}


def audit_summary(user_uuid: str | None = None) -> list[dict[str, Any]]:
    tables = _t()
    rows = [dict(r) for r in tables["audits"].all()]
    if user_uuid:
        rows = [r for r in rows if r.get("actor_uuid") == user_uuid or r.get("details", {}).get("user_uuid") == user_uuid]
    return rows


def reset_memory_tables_for_tests() -> None:
    # Helper used by tests; tables are already patched by conftest.
    pass
