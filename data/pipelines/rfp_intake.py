"""Dedicated LangGraph pipeline for RFP intake (Parte 1 de 3).

This graph is intentionally separate from the RAG and Manager support agent graphs.
It orchestrates transformations from data/process/rfp.py and returns structured
results; persistence is handled by the caller (services/api RFP domain).
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, TypedDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from data.process.rfp import (
    RfpBlockedError,
    build_handoff,
    classify_rfp,
    compute_readability,
    decompose_departments,
    extract_metadata,
    pdf_to_markdown,
    synthesize,
    worker_extract,
)


class RfpIntakeState(TypedDict, total=False):
    ticket_id: str
    storage_path: str
    markdown: str
    language: str
    metadata: dict[str, Any]
    readability: list[dict[str, Any]]
    classification: dict[str, Any]
    departments: list[str]
    department_results: list[dict[str, Any]]
    synthesis: dict[str, Any]
    handoff: dict[str, Any]
    outcome: str  # analisis_completo | descartado | blocked


def _convert(state: RfpIntakeState) -> RfpIntakeState:
    markdown = pdf_to_markdown(state["storage_path"])
    return {"markdown": markdown}


def _metadata(state: RfpIntakeState) -> RfpIntakeState:
    md = state["markdown"]
    lang = state.get("language", "unknown")
    fields = extract_metadata(md)
    metrics = compute_readability(md, language=lang)
    return {"metadata": fields, "readability": metrics}


def _classify(state: RfpIntakeState) -> RfpIntakeState:
    result = classify_rfp(state["markdown"], state.get("metadata", {}))
    return {"classification": result}


def _route_after_classify(state: RfpIntakeState) -> str:
    cls = state.get("classification", {})
    if cls.get("is_rfp"):
        return "orchestrate"
    return "discard"


def _discard(state: RfpIntakeState) -> RfpIntakeState:
    return {"outcome": "descartado"}


def _orchestrate(state: RfpIntakeState) -> RfpIntakeState:
    departments = decompose_departments(state["markdown"], state.get("metadata", {}))
    results: list[dict[str, Any]] = []
    for dept in departments:
        extracted = worker_extract(dept, state["markdown"], state.get("metadata", {}))
        results.append({"department": dept, **extracted})
    return {"departments": departments, "department_results": results}


def _synthesize(state: RfpIntakeState) -> RfpIntakeState:
    synthesis = synthesize(state["ticket_id"], state.get("department_results", []))
    handoff = build_handoff(state["ticket_id"], synthesis, state.get("department_results", []))
    return {"synthesis": synthesis, "handoff": handoff, "outcome": "analisis_completo"}


def build_graph():
    try:
        from langgraph.graph import END, StateGraph
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"LangGraph not available: {exc}")

    graph = StateGraph(RfpIntakeState)
    graph.add_node("convert", _convert)
    graph.add_node("metadata", _metadata)
    graph.add_node("classify", _classify)
    graph.add_node("discard", _discard)
    graph.add_node("orchestrate", _orchestrate)
    graph.add_node("synthesize", _synthesize)

    graph.set_entry_point("convert")
    graph.add_edge("convert", "metadata")
    graph.add_edge("metadata", "classify")
    graph.add_conditional_edges("classify", _route_after_classify, {"orchestrate": "orchestrate", "discard": "discard"})
    graph.add_edge("orchestrate", "synthesize")
    graph.add_edge("discard", END)
    graph.add_edge("synthesize", END)

    return graph.compile()


def run_rfp_intake(ticket_id: str, storage_path: str, language: str = "unknown") -> dict[str, Any]:
    graph = build_graph()
    initial: RfpIntakeState = {
        "ticket_id": ticket_id,
        "storage_path": storage_path,
        "language": language,
        "outcome": "analizando",
    }
    result = graph.invoke(initial)
    return dict(result)


if __name__ == "__main__":
    import json

    if len(sys.argv) < 3:
        raise SystemExit("Usage: python -m data.pipelines.rfp_intake <ticket_id> <pdf_path>")
    out = run_rfp_intake(sys.argv[1], sys.argv[2])
    print(json.dumps({k: v for k, v in out.items() if k != "markdown"}, ensure_ascii=False, indent=2, default=str))
