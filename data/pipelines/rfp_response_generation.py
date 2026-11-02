"""Dedicated LangGraph pipeline for RFP response generation (Parte 2 de 3).

Separate from rfp_intake (Parte 1) and from the Manager support agent.
Persistence is handled by the caller (services/api RFP domain).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, TypedDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data.process.rfp_generation import (
    ConfigurationError,
    ProviderError,
    RfpGenerationSettings,
    assess_global_compliance,
    estimate_value_usd,
    evaluate_section,
    generate_sections_parallel,
    load_settings,
    prompt_hash,
)

MAX_DEFAULT = 3


class RfpResponseState(TypedDict, total=False):
    ticket_id: str
    active_departments: list[str]
    metadata: dict[str, Any]
    aspects_by_department: dict[str, list[dict[str, Any]]]
    max_iterations: int
    settings: RfpGenerationSettings
    drafts: dict[str, str]
    draft_iterations: dict[str, int]
    evaluations: dict[str, dict[str, Any]]
    approved: dict[str, bool]
    exhausted: list[str]
    global_compliance: dict[str, Any]
    requires_ceo_approval: bool
    open_questions: list[str]
    error_code: str | None
    error_detail: str | None
    outcome: str  # generacion_completa | needs_human_review | failed


def _prepare(state: RfpResponseState) -> RfpResponseState:
    departments = list(state.get("active_departments") or [])
    if not departments:
        return {"error_code": "no_active_departments", "error_detail": "No hay departamentos activos en el handoff.", "outcome": "failed"}
    settings = state.get("settings")
    if settings is None:
        settings = load_settings()
    return {
        "active_departments": departments,
        "settings": settings,
        "drafts": {},
        "draft_iterations": {},
        "evaluations": {},
        "approved": {},
        "exhausted": [],
        "max_iterations": int(state.get("max_iterations") or settings.max_iterations),
        "error_code": None,
        "error_detail": None,
    }


def _departments_to_generate(state: RfpResponseState) -> list[str]:
    approved = state.get("approved", {})
    exhausted = set(state.get("exhausted", []))
    iterations = state.get("draft_iterations", {})
    max_iter = int(state.get("max_iterations", MAX_DEFAULT))
    out = []
    for dept in state.get("active_departments", []):
        if approved.get(dept):
            continue
        if dept in exhausted:
            continue
        current = iterations.get(dept, 0)
        if current >= max_iter:
            continue
        out.append(dept)
    return out


def _generate(state: RfpResponseState) -> RfpResponseState:
    to_generate = _departments_to_generate(state)
    if not to_generate:
        return {}
    settings = state["settings"]
    metadata = state.get("metadata", {})
    aspects = state.get("aspects_by_department", {})
    iterations = dict(state.get("draft_iterations", {}))
    feedback_by_department = {}
    for dept in to_generate:
        ev = state.get("evaluations", {}).get(dept)
        if ev and not ev.get("overall_pass", False):
            feedback_by_department[dept] = ev.get("feedback_for_generator", "")
    # increment iteration counters
    for dept in to_generate:
        iterations[dept] = iterations.get(dept, 0) + 1

    try:
        new_drafts = generate_sections_parallel(
            to_generate,
            metadata,
            aspects,
            settings,
            feedback_by_department=feedback_by_department,
        )
    except (ConfigurationError, ProviderError) as exc:
        code = "configuration_missing" if isinstance(exc, ConfigurationError) else "provider_failed"
        return {"error_code": code, "error_detail": str(exc)[:1000], "outcome": "failed"}

    drafts = dict(state.get("drafts", {}))
    for dept, content in new_drafts.items():
        drafts[dept] = content
    return {"drafts": drafts, "draft_iterations": iterations}


def _evaluate(state: RfpResponseState) -> RfpResponseState:
    to_eval = []
    iterations = state.get("draft_iterations", {})
    approved = dict(state.get("approved", {}))
    evaluations = dict(state.get("evaluations", {}))
    drafts = state.get("drafts", {})
    settings = state["settings"]
    aspects = state.get("aspects_by_department", {})
    exhausted = list(state.get("exhausted", []))
    max_iter = int(state.get("max_iterations", MAX_DEFAULT))

    for dept in state.get("active_departments", []):
        if approved.get(dept):
            continue
        if dept in exhausted:
            continue
        if dept not in drafts:
            continue
        # evaluate only if iteration not yet evaluated
        current_iter = iterations.get(dept, 0)
        existing = evaluations.get(dept)
        if existing and existing.get("iteration") == current_iter:
            continue
        to_eval.append(dept)

    for dept in to_eval:
        result = evaluate_section(
            dept,
            drafts[dept],
            aspects.get(dept, []),
            iterations.get(dept, 0),
            settings,
        )
        evaluations[dept] = {
            "section_id": result.section_id,
            "department_id": result.department_id,
            "iteration": result.iteration,
            "readability": result.readability,
            "relevance": result.relevance,
            "compliance": result.compliance,
            "overall_pass": result.overall_pass,
            "feedback_for_generator": result.feedback_for_generator,
        }
        approved[dept] = bool(result.overall_pass)
        if not result.overall_pass and iterations.get(dept, 0) >= max_iter:
            if dept not in exhausted:
                exhausted.append(dept)

    return {"evaluations": evaluations, "approved": approved, "exhausted": exhausted}


def _route(state: RfpResponseState) -> str:
    if state.get("error_code"):
        return "finalize"
    approved = state.get("approved", {})
    exhausted = set(state.get("exhausted", []))
    iterations = state.get("draft_iterations", {})
    max_iter = int(state.get("max_iterations", MAX_DEFAULT))
    for dept in state.get("active_departments", []):
        if approved.get(dept):
            continue
        if dept in exhausted:
            continue
        if iterations.get(dept, 0) < max_iter:
            return "generate"
    return "finalize"


def _finalize(state: RfpResponseState) -> RfpResponseState:
    if state.get("error_code"):
        return {"outcome": "failed"}
    drafts = state.get("drafts", {})
    evaluations = state.get("evaluations", {})
    approved = state.get("approved", {})
    settings = state["settings"]
    metadata = state.get("metadata", {})
    all_approved = all(approved.get(d, False) for d in state.get("active_departments", []))

    estimated = estimate_value_usd(metadata)
    global_result, requires_ceo, _ = assess_global_compliance(drafts, estimated, settings)

    open_questions = []
    if not metadata.get("budget_range"):
        open_questions.append("Presupuesto no especificado en la RFP")
    if not metadata.get("scope"):
        open_questions.append("Alcance/volumen no definido")
    if settings.fx_rate_usd_cop is None:
        open_questions.append("Tasa de conversión USD/COP no configurada; no se realizaron conversiones.")

    outcome = "generacion_completa" if all_approved else "needs_human_review"
    return {
        "global_compliance": {
            "pass": global_result.pass_,
            "rule_ids": global_result.rule_ids,
            "violations": global_result.violations,
            "details": global_result.details,
        },
        "requires_ceo_approval": bool(requires_ceo),
        "open_questions": open_questions,
        "outcome": outcome,
    }


def build_graph():
    try:
        from langgraph.graph import END, StateGraph
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LangGraph not available: {exc}")

    graph = StateGraph(RfpResponseState)
    graph.add_node("prepare", _prepare)
    graph.add_node("generate", _generate)
    graph.add_node("evaluate", _evaluate)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "generate")
    graph.add_edge("generate", "evaluate")
    graph.add_conditional_edges("evaluate", _route, {"generate": "generate", "finalize": "finalize"})
    graph.add_edge("finalize", END)
    return graph.compile()


def run_rfp_response_generation(
    ticket_id: str,
    active_departments: list[str],
    metadata: dict[str, Any],
    aspects_by_department: dict[str, list[dict[str, Any]]],
    max_iterations: int | None = None,
    settings: RfpGenerationSettings | None = None,
) -> dict[str, Any]:
    graph = build_graph()
    cfg = settings or load_settings()
    initial: RfpResponseState = {
        "ticket_id": ticket_id,
        "active_departments": active_departments,
        "metadata": metadata or {},
        "aspects_by_department": aspects_by_department or {},
        "max_iterations": int(max_iterations or cfg.max_iterations),
        "settings": cfg,
    }
    result = graph.invoke(initial)
    return dict(result)