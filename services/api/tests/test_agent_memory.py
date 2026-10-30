"""Tests for MEM-092 Part 1 agent memory (isolated storage)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.domains.agent import memory as M
from app.domains.agent.memory import MemoryPolicy


POLICY = MemoryPolicy(allowed_categories=frozenset({"preference"}), max_active_per_user=2, pending_ttl_hours=1)


def test_propose_does_not_consolidate():
    proposal = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "Prefiere alertas por WhatsApp", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    assert proposal is not None
    assert proposal.status == "pending"
    assert M.read_relevant_memories("u1", "c1", "alertas", policy=POLICY) == []


def test_approve_consolidates_and_dedups():
    p = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "Prefiere alertas por WhatsApp", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    resolved = M.resolve_proposal(p.proposal_id, "u1", "approve", policy=POLICY, user_uuid="u1")
    assert resolved.status == "consolidated"
    mems = M.read_relevant_memories("u1", "c1", "alertas whatsapp", policy=POLICY)
    assert len(mems) == 1
    # duplicate proposal should dedup
    p2 = M.propose_memory("u1", "c1", "run2", {"should_remember": True, "fact": "Prefiere alertas por WhatsApp", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    M.resolve_proposal(p2.proposal_id, "u1", "approve", policy=POLICY, user_uuid="u1")
    mems2 = M.read_relevant_memories("u1", "c1", "alertas whatsapp", policy=POLICY)
    assert len(mems2) == 1


def test_reject_does_not_change_memory():
    p = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "No guardar esto", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    # category not allowed? preference allowed, fact ok
    resolved = M.resolve_proposal(p.proposal_id, "u1", "reject", policy=POLICY, user_uuid="u1")
    assert resolved.status == "rejected"
    assert M.read_relevant_memories("u1", "c1", "guardar", policy=POLICY) == []


def test_edit_creates_revised_pending():
    p = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "Original", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    resolved = M.resolve_proposal(p.proposal_id, "u1", "edit", revised_fact="Revisado", policy=POLICY, user_uuid="u1")
    assert resolved.status == "edited"
    pending = M.get_pending_proposal("c1", "u1")
    assert pending is not None
    assert pending.proposed_fact == "Revisado"
    assert pending.status == "pending"


def test_ambiguous_expires():
    p = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "Ambiguo", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    resolved = M.resolve_proposal(p.proposal_id, "u1", "ambiguous", policy=POLICY, user_uuid="u1")
    assert resolved.status == "expired"


def test_isolation_between_users_and_conversations():
    p = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "Secreto u1", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    # user2 cannot see pending
    assert M.get_pending_proposal("c1", "u2") is None
    M.resolve_proposal(p.proposal_id, "u1", "approve", policy=POLICY, user_uuid="u1")
    assert M.read_relevant_memories("u2", "c1", "secreto", policy=POLICY) == []


def test_policy_denies_unknown_category():
    proposal = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "x", "category": "secret", "rationale": "r", "confidence": 0.9}, policy=POLICY)
    assert proposal is None


def test_low_confidence_denied():
    proposal = M.propose_memory("u1", "c1", "run1", {"should_remember": True, "fact": "x", "category": "preference", "rationale": "r", "confidence": 0.1}, policy=POLICY)
    assert proposal is None


def test_limit_eviction():
    policy = MemoryPolicy(allowed_categories=frozenset({"preference"}), max_active_per_user=2, pending_ttl_hours=1)
    for i in range(3):
        p = M.propose_memory("u1", "c1", f"run{i}", {"should_remember": True, "fact": f"Facto numero {i}", "category": "preference", "rationale": "r", "confidence": 0.9}, policy=policy)
        M.resolve_proposal(p.proposal_id, "u1", "approve", policy=policy, user_uuid="u1")
    # only 2 active
    all_active = [r for r in M.memories_table.all() if r.get("user_uuid") == "u1" and r.get("status") == "active"]
    assert len(all_active) <= 2


def test_expired_memory_not_returned():
    # insert expired memory manually
    M.memories_table.insert({
        "memory_id": "mem-expired",
        "user_uuid": "u1",
        "conversation_id": "c1",
        "scope": "user",
        "category": "preference",
        "fact": "Expirado",
        "content_hash": "h",
        "source_run_id": None,
        "status": "active",
        "created_at": "2020-01-01T00:00:00+00:00",
        "updated_at": "2020-01-01T00:00:00+00:00",
        "expires_at": "2020-01-02T00:00:00+00:00",
        "last_used_at": None,
        "supersedes": [],
    })
    assert M.read_relevant_memories("u1", "c1", "expirado", policy=POLICY) == []


def test_classify_proposal_response():
    pending = M.MemoryProposal(
        proposal_id="p", user_uuid="u1", conversation_id="c1", origin_run_id=None,
        proposed_fact="f", category="preference", rationale="r", confidence=0.9,
        status="pending", created_at=_now_iso(), expires_at=_now_iso(),
    )
    c = M.classify_proposal_response("sí", pending)
    assert c.decision == "approve"
    c2 = M.classify_proposal_response("no", pending)
    assert c2.decision == "reject"
    c3 = M.classify_proposal_response("edita: nuevo texto", pending)
    assert c3.decision == "edit"
    assert c3.revised_fact is not None


def _now_iso():
    return datetime.now(timezone.utc).isoformat()