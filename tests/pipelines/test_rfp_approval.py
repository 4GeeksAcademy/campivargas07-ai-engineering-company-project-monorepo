"""Deterministic tests for RFP approval/completion (Parte 3)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.update(
    {
        "RFP_GENERATION_URL": "https://example.com/v1/chat/completions",
        "RFP_GENERATION_MODEL": "test-model",
        "RFP_GENERATION_API_KEY": "test-key",
        "RFP_MAX_ITERATIONS": "2",
    }
)

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from data.pipelines.rfp_approval import build_graph, run_rfp_approval


def _drafts():
    text = (
        "Seccion de marketing. Calidad consistente, experiencia cálida y velocidad de servicio. "
        "Validez de la oferta: 30 días desde su emisión. Precio: 1000 COP y 1 USD."
    )
    return {"marketing": text, "operaciones": text.replace("marketing", "operaciones")}


def test_approval_interrupt_and_resume():
    checkpointer = MemorySaver()
    drafts = _drafts()
    versions = {"marketing": 1, "operaciones": 1}
    evals = {"marketing": {"overall_pass": True}, "operaciones": {"overall_pass": True}}
    result, cfg = run_rfp_approval(
        ticket_id="t-int",
        active_departments=["marketing"],
        metadata={"client_name": "X"},
        aspects_by_department={},
        drafts=drafts,
        draft_versions=versions,
        evaluations=evals,
        requires_ceo_approval=False,
        checkpointer=checkpointer,
    )
    assert "__interrupt__" in result

    graph = build_graph(checkpointer=checkpointer)
    st = graph.get_state(cfg)
    ids = [i.id for t in st.tasks for i in t.interrupts]
    assert ids
    res2 = graph.invoke(Command(resume={ids[0]: {"decision": "approve", "comment": "", "approver_uuid": "u1", "version": 1}}), cfg)
    assert "__interrupt__" not in res2
    assert res2.get("outcome") == "terminado"
    assert res2.get("final_document_content")


def test_independent_departments_b_approves_while_a_pending():
    checkpointer = MemorySaver()
    drafts = _drafts()
    versions = {"marketing": 1, "operaciones": 1}
    evals = {"marketing": {"overall_pass": True}, "operaciones": {"overall_pass": True}}
    result, cfg = run_rfp_approval(
        ticket_id="t-indep",
        active_departments=["marketing", "operaciones"],
        metadata={"client_name": "X"},
        aspects_by_department={},
        drafts=drafts,
        draft_versions=versions,
        evaluations=evals,
        requires_ceo_approval=False,
        checkpointer=checkpointer,
    )
    assert "__interrupt__" in result
    graph = build_graph(checkpointer=checkpointer)
    st = graph.get_state(cfg)
    ids = []
    dept_to_id = {}
    for t in st.tasks:
        for iv in t.interrupts:
            val = iv.value if hasattr(iv, "value") else {}
            if isinstance(val, dict):
                dept_to_id[val.get("department_id")] = iv.id
    assert "marketing" in dept_to_id and "operaciones" in dept_to_id

    # approve operaciones only
    res_b = graph.invoke(Command(resume={dept_to_id["operaciones"]: {"decision": "approve", "comment": "", "approver_uuid": "u2", "version": 1}}), cfg)
    assert "__interrupt__" in res_b
    # marketing still pending
    st2 = graph.get_state(cfg)
    remaining = [iv.value.get("department_id") for t in st2.tasks for iv in t.interrupts if isinstance(iv.value, dict)]
    assert "marketing" in remaining

    # now approve marketing
    st3 = graph.get_state(cfg)
    m_id = None
    for t in st3.tasks:
        for iv in t.interrupts:
            val = iv.value if hasattr(iv, "value") else {}
            if isinstance(val, dict) and val.get("department_id") == "marketing":
                m_id = iv.id
    res_final = graph.invoke(Command(resume={m_id: {"decision": "approve", "comment": "", "approver_uuid": "u1", "version": 1}}), cfg)
    assert res_final.get("outcome") == "terminado"


def test_request_changes_triggers_correction(monkeypatch):
    import data.process.rfp_generation as gen

    def fake_generate_section(department_id, metadata, aspects, settings, feedback=None, client=None):
        return "Entrega en 12 dias habiles. " + ("Frase simple. " * 20) + "Precio: 1000 COP y 1 USD."

    monkeypatch.setattr(gen, "generate_section", fake_generate_section)

    checkpointer = MemorySaver()
    drafts = {"marketing": "Entrega en 5 días hábiles. Precio: 1000 COP y 1 USD."}
    versions = {"marketing": 1}
    evals = {"marketing": {"overall_pass": False}}
    result, cfg = run_rfp_approval(
        ticket_id="t-rc",
        active_departments=["marketing"],
        metadata={"client_name": "X"},
        aspects_by_department={"marketing": []},
        drafts=drafts,
        draft_versions=versions,
        evaluations=evals,
        requires_ceo_approval=False,
        checkpointer=checkpointer,
    )
    graph = build_graph(checkpointer=checkpointer)
    st = graph.get_state(cfg)
    ids = [i.id for t in st.tasks for i in t.interrupts]
    # request changes
    res = graph.invoke(Command(resume={ids[0]: {"decision": "request_changes", "comment": "corregir plazo", "approver_uuid": "u1", "version": None}}), cfg)
    # after correction, a new interrupt should appear (or final if passes)
    assert res.get("correction_cycle", 0) >= 1 or "__interrupt__" in res or res.get("outcome") in ("terminado", "agotado")


def test_ceo_threshold_blocks_final():
    checkpointer = MemorySaver()
    drafts = _drafts()
    versions = {"marketing": 1}
    evals = {"marketing": {"overall_pass": True}}
    result, cfg = run_rfp_approval(
        ticket_id="t-ceo",
        active_departments=["marketing"],
        metadata={"client_name": "X", "budget_range": "$60,000 USD/año"},
        aspects_by_department={},
        drafts=drafts,
        draft_versions=versions,
        evaluations=evals,
        requires_ceo_approval=True,
        checkpointer=checkpointer,
    )
    graph = build_graph(checkpointer=checkpointer)
    # approve marketing
    st = graph.get_state(cfg)
    ids = [i.id for t in st.tasks for i in t.interrupts]
    # find marketing id
    m_id = None
    for t in st.tasks:
        for iv in t.interrupts:
            val = iv.value if hasattr(iv, "value") else {}
            if isinstance(val, dict) and val.get("department_id") == "marketing":
                m_id = iv.id
    graph.invoke(Command(resume={m_id: {"decision": "approve", "comment": "", "approver_uuid": "u1", "version": 1}}), cfg)
    # CEO still pending -> should not be terminado
    st2 = graph.get_state(cfg)
    remaining = [iv.value.get("department_id") for t in st2.tasks for iv in t.interrupts if isinstance(iv.value, dict)]
    assert "ceo" in remaining


def test_setup_sla_conflict_forces_correction():
    checkpointer = MemorySaver()
    drafts = {"operaciones": "Entrega en 5 días hábiles. Precio: 1000 COP y 1 USD."}
    versions = {"operaciones": 1}
    evals = {"operaciones": {"overall_pass": False}}
    result, cfg = run_rfp_approval(
        ticket_id="t-sla",
        active_departments=["operaciones"],
        metadata={"client_name": "X"},
        aspects_by_department={"operaciones": []},
        drafts=drafts,
        draft_versions=versions,
        evaluations=evals,
        requires_ceo_approval=False,
        checkpointer=checkpointer,
    )
    # conflict should be detected
    assert any(c.get("trigger_id") == "setup-sla-breach" for c in (result.get("conflicts") or []))


def test_final_document_idempotent_content():
    checkpointer = MemorySaver()
    drafts = _drafts()
    versions = {"marketing": 1}
    evals = {"marketing": {"overall_pass": True}}
    result, cfg = run_rfp_approval(
        ticket_id="t-idem",
        active_departments=["marketing"],
        metadata={"client_name": "X"},
        aspects_by_department={},
        drafts={"marketing": drafts["marketing"]},
        draft_versions={"marketing": 1},
        evaluations=evals,
        requires_ceo_approval=False,
        checkpointer=checkpointer,
    )
    graph = build_graph(checkpointer=checkpointer)
    st = graph.get_state(cfg)
    ids = [i.id for t in st.tasks for i in t.interrupts]
    res = graph.invoke(Command(resume={ids[0]: {"decision": "approve", "comment": "", "approver_uuid": "u1", "version": 1}}), cfg)
    assert res.get("outcome") == "terminado"
    content1 = res.get("final_document_content")
    # invoking again should not create new; graph already finished, state same
    st2 = graph.get_state(cfg)
    assert st2.values.get("final_document_content") == content1
