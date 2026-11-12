"""Dedicated LangGraph pipeline for RFP human approval and completion (Parte 3 de 3).

Separate from rfp_intake (Parte 1) and rfp_response_generation (Parte 2).
Persistence of checkpoints is handled by the caller via a persistent checkpointer.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Any, TypedDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data.process.rfp_generation import (
    RfpGenerationSettings,
    check_fast_setup,
    evaluate_section,
    generate_sections_parallel,
    load_settings,
)


def _merge_dict(a: Any, b: Any) -> dict:
    out = dict(a or {})
    out.update(b or {})
    return out


def _merge_list(a: Any, b: Any) -> list:
    return list(a or []) + list(b or [])


class RfpApprovalState(TypedDict, total=False):
    ticket_id: str
    active_departments: list[str]
    metadata: dict[str, Any]
    aspects_by_department: dict[str, list[dict[str, Any]]]
    drafts: dict[str, str]
    draft_versions: dict[str, int]
    evaluations: dict[str, dict[str, Any]]
    approvals: Annotated[dict[str, dict[str, Any]], _merge_dict]
    sections_to_correct: list[str]
    conflicts: list[dict[str, Any]]
    requires_ceo_approval: bool
    ceo_approval: dict[str, Any]
    correction_cycle: int
    max_correction_cycles: int
    correction_exhausted: bool
    open_questions: list[str]
    global_compliance: dict[str, Any]
    final_document_content: str
    final_document_sections: list[dict[str, Any]]
    outcome: str  # esperando_aprobación | terminado | agotado | rechazado | failed
    error_code: str | None
    error_detail: str | None
    # per-branch (Send) inputs
    department_id: str


def _prepare(state: RfpApprovalState) -> RfpApprovalState:
    active = list(state.get("active_departments") or [])
    settings = load_settings()
    drafts = dict(state.get("drafts") or {})
    versions = dict(state.get("draft_versions") or {})
    evaluations = dict(state.get("evaluations") or {})
    approvals = dict(state.get("approvals") or {})
    for dept in active:
        approvals.setdefault(
            dept,
            {"status": "pendiente", "version": versions.get(dept, 1), "approver_uuid": None, "decided_at": None, "comment": "", "decision": None},
        )
    if state.get("requires_ceo_approval"):
        approvals.setdefault(
            "ceo",
            {"status": "pendiente", "version": None, "approver_uuid": None, "decided_at": None, "comment": "", "decision": None},
        )
    conflicts = list(state.get("conflicts") or [])
    return {
        "active_departments": active,
        "drafts": drafts,
        "draft_versions": versions,
        "evaluations": evaluations,
        "approvals": approvals,
        "sections_to_correct": list(state.get("sections_to_correct") or []),
        "conflicts": conflicts,
        "requires_ceo_approval": bool(state.get("requires_ceo_approval", False)),
        "ceo_approval": dict(state.get("ceo_approval") or {}),
        "correction_cycle": int(state.get("correction_cycle", 0)),
        "max_correction_cycles": int(state.get("max_correction_cycles", 3)),
        "correction_exhausted": bool(state.get("correction_exhausted", False)),
        "open_questions": list(state.get("open_questions") or []),
        "global_compliance": dict(state.get("global_compliance") or {}),
        "outcome": state.get("outcome") or "esperando_aprobación",
        "error_code": state.get("error_code"),
        "error_detail": state.get("error_detail"),
    }


def _detect_conflicts(state: RfpApprovalState) -> RfpApprovalState:
    conflicts: list[dict[str, Any]] = []
    active = state.get("active_departments", [])
    drafts = state.get("drafts", {})

    # setup-sla-breach
    for dept, content in (drafts or {}).items():
        violations = check_fast_setup(content or "")
        if violations:
            conflicts.append(
                {
                    "trigger_id": "setup-sla-breach",
                    "departments": [dept],
                    "summary": violations[0],
                    "arbiter": "Felipe Guerrero",
                    "status": "open",
                }
            )

    # cost-vs-feasibility (structured metrics; no free-text inference)
    metrics = (state.get("metadata") or {}).get("rfp_metrics", {}) or {}
    proc_cost = metrics.get("procurement_cost_per_event_usd")
    ops_price = metrics.get("operations_implied_price_usd")
    if "procurement" in active and "operaciones" in active:
        if proc_cost is not None and ops_price is not None:
            try:
                if float(proc_cost) > float(ops_price):
                    conflicts.append(
                        {
                            "trigger_id": "cost-vs-feasibility",
                            "departments": ["procurement", "operaciones"],
                            "summary": "El costo de procurement no soporta el precio implícito de operaciones.",
                            "arbiter": "Camila Ospina",
                            "status": "open",
                        }
                    )
            except (TypeError, ValueError):
                pass
        else:
            conflicts.append(
                {
                    "trigger_id": "cost-vs-feasibility",
                    "departments": ["procurement", "operaciones"],
                    "summary": "Métricas estructuradas ausentes; conflicto no evaluable (no se asume OK).",
                    "arbiter": "Camila Ospina",
                    "status": "not_evaluable",
                }
            )

    # ceo-threshold
    if state.get("requires_ceo_approval"):
        ceo_status = (state.get("approvals") or {}).get("ceo", {}).get("status")
        if ceo_status != "aprobado":
            conflicts.append(
                {
                    "trigger_id": "ceo-threshold",
                    "departments": ["ceo"],
                    "summary": "Valor anual superior a 50.000 USD y aprobación CEO pendiente.",
                    "arbiter": "Mariana Restrepo",
                    "status": "open",
                }
            )

    return {"conflicts": conflicts}


def _arbitrate(state: RfpApprovalState) -> RfpApprovalState:
    sections = set(state.get("sections_to_correct") or [])
    for c in state.get("conflicts", []) or []:
        tid = c.get("trigger_id")
        if tid in ("cost-vs-feasibility", "setup-sla-breach") and c.get("status") in ("open", "not_evaluable"):
            for d in c.get("departments", []):
                if d != "ceo":
                    sections.add(d)
    return {"sections_to_correct": sorted(sections)}


def _route_after_arbitrate(state: RfpApprovalState) -> str:
    if state.get("error_code"):
        return "finalize"
    sections = state.get("sections_to_correct") or []
    cycle = int(state.get("correction_cycle", 0))
    maxc = int(state.get("max_correction_cycles", 3))
    if sections and cycle < maxc:
        return "correct"
    if sections and cycle >= maxc:
        return "exhausted"
    return "approvals"


def _correct_sections(state: RfpApprovalState) -> RfpApprovalState:
    settings = load_settings()
    metadata = state.get("metadata", {}) or {}
    aspects = state.get("aspects_by_department", {}) or {}
    drafts = dict(state.get("drafts", {}) or {})
    versions = dict(state.get("draft_versions", {}) or {})
    evaluations = dict(state.get("evaluations", {}) or {})
    approvals = dict(state.get("approvals", {}) or {})
    to_fix = list(state.get("sections_to_correct") or [])
    feedback_map: dict[str, str] = {}
    for dept in to_fix:
        ap = approvals.get(dept, {})
        if ap.get("status") == "cambios_solicitados" and ap.get("comment"):
            feedback_map[dept] = str(ap.get("comment"))
        else:
            feedback_map[dept] = "Corregir según conflicto/arbitraje estructurado."

    try:
        new_drafts = generate_sections_parallel(to_fix, metadata, aspects, settings, feedback_by_department=feedback_map)
    except Exception as exc:  # noqa: BLE001
        return {"error_code": "provider_failed", "error_detail": str(exc)[:1000], "outcome": "failed"}

    for dept, content in (new_drafts or {}).items():
        versions[dept] = int(versions.get(dept, 1)) + 1
        drafts[dept] = content
        ev = evaluate_section(dept, content, aspects.get(dept, []), versions[dept], settings)
        evaluations[dept] = {
            "section_id": ev.section_id,
            "department_id": ev.department_id,
            "iteration": ev.iteration,
            "readability": ev.readability,
            "relevance": ev.relevance,
            "compliance": ev.compliance,
            "overall_pass": ev.overall_pass,
            "feedback_for_generator": ev.feedback_for_generator,
        }
        approvals[dept] = {
            "status": "pendiente",
            "version": versions[dept],
            "approver_uuid": None,
            "decided_at": None,
            "comment": "",
            "decision": None,
        }

    # mark structured conflicts resolved (except ceo-threshold)
    conflicts = []
    for c in state.get("conflicts", []) or []:
        cc = dict(c)
        if cc.get("trigger_id") in ("cost-vs-feasibility", "setup-sla-breach"):
            cc["status"] = "resolved"
        conflicts.append(cc)

    return {
        "drafts": drafts,
        "draft_versions": versions,
        "evaluations": evaluations,
        "approvals": approvals,
        "sections_to_correct": [],
        "conflicts": conflicts,
        "correction_cycle": int(state.get("correction_cycle", 0)) + 1,
    }


def _exhausted(state: RfpApprovalState) -> RfpApprovalState:
    return {"correction_exhausted": True, "outcome": "agotado"}


def _fanout(state: RfpApprovalState):
    from langgraph.types import Send

    sends = []
    snapshot = {
        "ticket_id": state.get("ticket_id"),
        "active_departments": state.get("active_departments", []),
        "metadata": state.get("metadata", {}),
        "aspects_by_department": state.get("aspects_by_department", {}),
        "drafts": state.get("drafts", {}),
        "draft_versions": state.get("draft_versions", {}),
        "evaluations": state.get("evaluations", {}),
        "approvals": state.get("approvals", {}),
        "conflicts": state.get("conflicts", []),
        "requires_ceo_approval": state.get("requires_ceo_approval", False),
        "global_compliance": state.get("global_compliance", {}),
        "open_questions": state.get("open_questions", []),
        "correction_cycle": state.get("correction_cycle", 0),
    }
    for dept in state.get("active_departments", []):
        sends.append(Send("human_approval", {**snapshot, "department_id": dept}))
    if state.get("requires_ceo_approval"):
        sends.append(Send("human_approval", {**snapshot, "department_id": "ceo"}))
    return sends


def _human_approval(state: RfpApprovalState) -> RfpApprovalState:
    from langgraph.types import interrupt

    dept = state["department_id"]
    drafts = state.get("drafts", {}) or {}
    versions = state.get("draft_versions", {}) or {}
    evaluations = state.get("evaluations", {}) or {}
    version = versions.get(dept) if dept != "ceo" else None

    payload = {
        "department_id": dept,
        "draft_id": None,
        "version": version,
        "content": drafts.get(dept) if dept != "ceo" else None,
        "evaluation_result": evaluations.get(dept) if dept != "ceo" else None,
        "global_compliance": state.get("global_compliance"),
        "open_questions": state.get("open_questions"),
        "conflicts": state.get("conflicts"),
        "requires_ceo_approval": state.get("requires_ceo_approval"),
    }
    decision = interrupt(payload)
    if not isinstance(decision, dict):
        decision = {"decision": str(decision)}

    dec = str(decision.get("decision", "")).strip().lower()
    if dec not in ("approve", "reject", "request_changes"):
        raise ValueError(f"Decisión inválida: {dec}")
    comment = str(decision.get("comment", "") or "")
    if dec in ("reject", "request_changes") and not comment.strip():
        raise ValueError("El comentario es obligatorio para reject/request_changes.")

    if dept != "ceo" and decision.get("version") is not None:
        if int(decision.get("version")) != int(version):
            raise ValueError(f"Versión obsoleta para {dept}: {decision.get('version')} != {version}.")

    status_map = {"approve": "aprobado", "reject": "rechazado", "request_changes": "cambios_solicitados"}
    approver_uuid = decision.get("approver_uuid")
    return {
        "approvals": {
            dept: {
                "status": status_map[dec],
                "version": version,
                "approver_uuid": approver_uuid,
                "decided_at": None,
                "comment": comment,
                "decision": dec,
            }
        },
    }


def _post_approval(state: RfpApprovalState) -> RfpApprovalState:
    approvals = state.get("approvals", {}) or {}
    rejected = [d for d, a in approvals.items() if (a or {}).get("status") == "rechazado"]
    changes = [d for d, a in approvals.items() if (a or {}).get("status") == "cambios_solicitados"]
    pending = [d for d, a in approvals.items() if (a or {}).get("status") == "pendiente"]

    conflicts = list(state.get("conflicts") or [])
    # resolve ceo-threshold if CEO approved
    if (approvals.get("ceo") or {}).get("status") == "aprobado":
        for c in conflicts:
            if c.get("trigger_id") == "ceo-threshold":
                c["status"] = "resolved"

    if rejected:
        return {"outcome": "rechazado", "conflicts": conflicts}
    if changes:
        return {"sections_to_correct": changes, "outcome": "esperando_aprobación", "conflicts": conflicts}
    if pending:
        return {"outcome": "esperando_aprobación", "conflicts": conflicts}
    open_conflicts = [c for c in conflicts if c.get("status") == "open"]
    if open_conflicts:
        return {"outcome": "esperando_aprobación", "conflicts": conflicts}
    return {"outcome": "listo_para_sintesis", "conflicts": conflicts}


def _route_after_approval(state: RfpApprovalState) -> str:
    if state.get("outcome") == "rechazado":
        return "finalize"
    sections = state.get("sections_to_correct") or []
    cycle = int(state.get("correction_cycle", 0))
    maxc = int(state.get("max_correction_cycles", 3))
    if sections and cycle < maxc:
        return "correct"
    if sections and cycle >= maxc:
        return "exhausted"
    if state.get("outcome") == "esperando_aprobación":
        # pending or open conflicts
        open_conflicts = [c for c in (state.get("conflicts") or []) if c.get("status") == "open"]
        if open_conflicts:
            return "exhausted" if cycle >= maxc else "approvals"
        return "approvals"
    return "finalize"


def _finalize(state: RfpApprovalState) -> RfpApprovalState:
    if state.get("outcome") in ("rechazado", "agotado"):
        return {"outcome": state.get("outcome")}
    approvals = state.get("approvals", {}) or {}
    if any((a or {}).get("status") != "aprobado" for a in approvals.values()):
        return {"outcome": "esperando_aprobación"}
    open_conflicts = [c for c in (state.get("conflicts") or []) if c.get("status") == "open"]
    if open_conflicts:
        return {"outcome": "esperando_aprobación"}
    gc = state.get("global_compliance") or {}
    if gc and gc.get("pass") is False:
        return {"outcome": "needs_human_review"}

    drafts = state.get("drafts", {}) or {}
    versions = state.get("draft_versions", {}) or {}
    sections_list = []
    for dept in state.get("active_departments", []):
        sections_list.append(
            {
                "department_id": dept,
                "version": versions.get(dept),
                "content": drafts.get(dept, ""),
            }
        )

    lines = [f"# Propuesta RFP — Ticket {state.get('ticket_id')}"]
    lines.append("")
    lines.append(f"Departamentos activos: {', '.join(state.get('active_departments', []))}")
    lines.append("")
    for s in sections_list:
        lines.append(f"## Sección: {s['department_id']} (v{s['version']})")
        lines.append("")
        lines.append(s.get("content", "") or "")
        lines.append("")
    gc = state.get("global_compliance") or {}
    lines.append("## Cumplimiento global")
    lines.append(f"- pass: {gc.get('pass')}")
    lines.append(f"- rule_ids: {', '.join(gc.get('rule_ids', []) or [])}")
    if gc.get("violations"):
        lines.append(f"- violations: {'; '.join(gc.get('violations', []))}")
    lines.append("")
    oq = state.get("open_questions") or []
    if oq:
        lines.append("## Preguntas abiertas")
        for q in oq:
            lines.append(f"- {q}")
        lines.append("")
    lines.append("Validez de la oferta: 30 días desde su emisión.")
    content = "\n".join(lines).strip() + "\n"

    return {
        "final_document_content": content,
        "final_document_sections": sections_list,
        "outcome": "terminado",
    }


def build_graph(checkpointer=None):
    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LangGraph not available: {exc}")

    graph = StateGraph(RfpApprovalState)
    graph.add_node("prepare", _prepare)
    graph.add_node("detect_conflicts", _detect_conflicts)
    graph.add_node("arbitrate", _arbitrate)
    graph.add_node("correct", _correct_sections)
    graph.add_node("exhausted", _exhausted)
    graph.add_node("human_approval", _human_approval)
    graph.add_node("post_approval", _post_approval)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "detect_conflicts")
    graph.add_edge("detect_conflicts", "arbitrate")
    graph.add_conditional_edges(
        "arbitrate",
        _route_after_arbitrate,
        {"correct": "correct", "exhausted": "exhausted", "approvals": "fanout_dummy"},
    )
    # fanout is handled by a conditional edge returning Send; add a dummy node? Instead use direct conditional from arbitrate with Send.
    # We'll replace above: remove dummy by re-adding properly.
    graph.add_edge("correct", "detect_conflicts")
    graph.add_edge("exhausted", "finalize")
    graph.add_edge("human_approval", "post_approval")
    graph.add_conditional_edges(
        "post_approval",
        _route_after_approval,
        {"correct": "correct", "exhausted": "exhausted", "approvals": "fanout_dummy2", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)

    compiled = graph.compile(checkpointer=checkpointer) if checkpointer is not None else graph.compile()
    return compiled


# LangGraph conditional edges cannot return Send from a node that is not registered? They can, but the target list must include the node names.
# We need a fanout edge. Rebuild with proper fanout by monkeypatching conditional edge functions at compile time is not possible.
# Instead, provide a wrapper builder that adds fanout conditional edges using Send.
def build_graph_with_fanout(checkpointer=None):
    try:
        from langgraph.graph import END, START, StateGraph
        from langgraph.types import Send
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LangGraph not available: {exc}")

    graph = StateGraph(RfpApprovalState)
    graph.add_node("prepare", _prepare)
    graph.add_node("detect_conflicts", _detect_conflicts)
    graph.add_node("arbitrate", _arbitrate)
    graph.add_node("correct", _correct_sections)
    graph.add_node("exhausted", _exhausted)
    graph.add_node("human_approval", _human_approval)
    graph.add_node("post_approval", _post_approval)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "detect_conflicts")
    graph.add_edge("detect_conflicts", "arbitrate")

    def _arbitrate_edge(state):
        r = _route_after_arbitrate(state)
        if r == "approvals":
            return _fanout(state)
        return r

    graph.add_conditional_edges("arbitrate", _arbitrate_edge, ["human_approval", "correct", "exhausted", "finalize"])
    # To be safe, use a router returning strings and handle fanout in a dedicated node instead.

    graph.add_edge("correct", "detect_conflicts")
    graph.add_edge("exhausted", "finalize")
    graph.add_edge("human_approval", "post_approval")

    def _post_edge(state):
        r = _route_after_approval(state)
        if r == "approvals":
            return _fanout(state)
        return r

    graph.add_conditional_edges("post_approval", _post_edge, ["human_approval", "correct", "exhausted", "finalize"])
    graph.add_edge("finalize", END)

    compiled = graph.compile(checkpointer=checkpointer) if checkpointer is not None else graph.compile()
    return compiled


def build_graph(checkpointer=None):
    # Use fanout-capable builder.
    return build_graph_with_fanout(checkpointer=checkpointer)


def run_rfp_approval(
    ticket_id: str,
    active_departments: list[str],
    metadata: dict[str, Any],
    aspects_by_department: dict[str, list[dict[str, Any]]],
    drafts: dict[str, str],
    draft_versions: dict[str, int],
    evaluations: dict[str, dict[str, Any]],
    requires_ceo_approval: bool,
    global_compliance: dict[str, Any] | None = None,
    open_questions: list[str] | None = None,
    max_correction_cycles: int = 3,
    settings=None,
    checkpointer=None,
):
    if settings is None:
        settings = load_settings()
    graph = build_graph(checkpointer=checkpointer)
    initial: RfpApprovalState = {
        "ticket_id": ticket_id,
        "active_departments": active_departments,
        "metadata": metadata or {},
        "aspects_by_department": aspects_by_department or {},
        "drafts": drafts or {},
        "draft_versions": draft_versions or {},
        "evaluations": evaluations or {},
        "requires_ceo_approval": bool(requires_ceo_approval),
        "global_compliance": global_compliance or {},
        "open_questions": open_questions or [],
        "max_correction_cycles": int(max_correction_cycles),
        "correction_cycle": 0,
    }
    config = {"configurable": {"thread_id": f"rfp-{ticket_id}"}}
    result = graph.invoke(initial, config)
    return dict(result), config