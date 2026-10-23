"""LangGraph state machine for Brasaland's RAG support agent (Part 1)."""
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any, Literal
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.domains.agent.state import AgentState, StateValidationError, validate_agent_state
from app.domains.agent.traces import sanitize_chunk_summary, save_trace
from data.pipelines.rag import generate_answer, retrieve
from data.process.config import (
    ConfigurationError,
    ProviderError,
    RagError,
    Settings,
    StoreError,
    settings,
)

MAX_QUESTION_LENGTH = 2000


class InvalidQuestionError(RagError):
    """Raised when the agent graph rejects an empty or out-of-bounds question."""


def route_after_receive(
    state: AgentState,
) -> Literal["reject_invalid_question", "retrieve_context"]:
    validate_agent_state(state)
    if state.get("route") == "empty_question":
        return "reject_invalid_question"
    return "retrieve_context"


def route_after_retrieve(
    state: AgentState,
) -> Literal["generate_grounded_answer", "abstain_without_evidence"]:
    validate_agent_state(state)
    context = state.get("retrieved_context") or []
    if len(context) > 0 and state.get("route") == "grounded":
        return "generate_grounded_answer"
    return "abstain_without_evidence"


def _classify_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, InvalidQuestionError):
        return ("INVALID_QUESTION", "La pregunta debe tener entre 1 y 2000 caracteres.")
    if isinstance(exc, ConfigurationError):
        return ("CONFIGURATION_ERROR", "La base de conocimiento aún no está configurada.")
    if isinstance(exc, ProviderError):
        return ("PROVIDER_ERROR", "No se pudo generar la respuesta. Inténtalo de nuevo.")
    if isinstance(exc, StoreError):
        return ("STORE_ERROR", "La base de conocimiento no está disponible. Inténtalo de nuevo.")
    if isinstance(exc, RagError):
        return ("RAG_ERROR", "La base de conocimiento no está disponible. Inténtalo de nuevo.")
    if isinstance(exc, StateValidationError):
        return ("STATE_VALIDATION_ERROR", "El estado del grafo no cumple el contrato esperado.")
    return ("INTERNAL_AGENT_ERROR", "Error interno al ejecutar el agente de soporte.")


def build_agent_graph(
    *,
    checkpointer: Any = None,
    retrieve_fn: Callable[..., list[dict[str, Any]]] = retrieve,
    generate_fn: Callable[..., str] = generate_answer,
    config_fn: Callable[[], Settings] = settings,
    step_observer: Callable[[str, dict[str, Any], float], None] | None = None,
):
    """Build and explicitly compile the Brasaland support agent StateGraph."""

    def _observe(node_name: str, update: dict[str, Any], started: float) -> dict[str, Any]:
        validate_agent_state(update)
        if step_observer is not None:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
            step_observer(node_name, update, duration_ms)
        return update

    def receive_question(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        run_id = (state.get("run_id") or f"run-{uuid4().hex[:12]}").strip()
        raw_question = state.get("question")
        cleaned = raw_question.strip() if isinstance(raw_question, str) else ""
        if not cleaned or len(cleaned) > MAX_QUESTION_LENGTH:
            return _observe(
                "receive_question",
                {
                    "run_id": run_id,
                    "question": cleaned,
                    "retrieved_context": [],
                    "route": "empty_question",
                    "error_code": "INVALID_QUESTION",
                },
                started,
            )
        return _observe(
            "receive_question",
            {
                "run_id": run_id,
                "question": cleaned,
                "retrieved_context": [],
                "route": "valid",
                "error_code": None,
            },
            started,
        )

    def reject_invalid_question(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        return _observe(
            "reject_invalid_question",
            {
                "answer": "",
                "route": "empty_question",
                "error_code": state.get("error_code") or "INVALID_QUESTION",
            },
            started,
        )

    def retrieve_context(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        cfg = config_fn()
        question = state["question"]
        chunks = retrieve_fn(question, k=5, min_score=cfg.min_score, config=cfg)
        route: Literal["grounded", "no_evidence"] = "grounded" if chunks else "no_evidence"
        return _observe(
            "retrieve_context",
            {
                "retrieved_context": chunks,
                "route": route,
            },
            started,
        )

    def generate_grounded_answer(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        cfg = config_fn()
        context = state.get("retrieved_context") or []
        answer = generate_fn(state["question"], context, config=cfg)
        return _observe(
            "generate_grounded_answer",
            {
                "answer": answer,
                "route": "grounded",
                "error_code": None,
            },
            started,
        )

    def abstain_without_evidence(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        cfg = config_fn()
        answer = generate_fn(state["question"], [], config=cfg)
        return _observe(
            "abstain_without_evidence",
            {
                "answer": answer,
                "route": "no_evidence",
                "error_code": None,
            },
            started,
        )

    workflow = StateGraph(AgentState)
    workflow.add_node("receive_question", receive_question)
    workflow.add_node("reject_invalid_question", reject_invalid_question)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_grounded_answer", generate_grounded_answer)
    workflow.add_node("abstain_without_evidence", abstain_without_evidence)

    workflow.add_edge(START, "receive_question")
    workflow.add_conditional_edges(
        "receive_question",
        route_after_receive,
        {
            "reject_invalid_question": "reject_invalid_question",
            "retrieve_context": "retrieve_context",
        },
    )
    workflow.add_conditional_edges(
        "retrieve_context",
        route_after_retrieve,
        {
            "generate_grounded_answer": "generate_grounded_answer",
            "abstain_without_evidence": "abstain_without_evidence",
        },
    )
    workflow.add_edge("reject_invalid_question", END)
    workflow.add_edge("generate_grounded_answer", END)
    workflow.add_edge("abstain_without_evidence", END)

    active_checkpointer = checkpointer if checkpointer is not None else InMemorySaver()
    return workflow.compile(checkpointer=active_checkpointer)


DEFAULT_CHECKPOINTER = InMemorySaver()
COMPILED_AGENT_GRAPH = build_agent_graph(checkpointer=DEFAULT_CHECKPOINTER)


def get_run_state(thread_id: str, *, graph: Any = COMPILED_AGENT_GRAPH) -> dict[str, Any]:
    """Return the latest checkpointed state snapshot for a given thread_id."""
    snapshot = graph.get_state({"configurable": {"thread_id": thread_id}})
    checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
    return {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id,
        "values": dict(snapshot.values) if snapshot.values else {},
        "next": list(snapshot.next) if snapshot.next else [],
        "step": snapshot.metadata.get("step") if isinstance(snapshot.metadata, dict) else None,
    }


def get_run_checkpoints(thread_id: str, *, graph: Any = COMPILED_AGENT_GRAPH) -> list[dict[str, Any]]:
    """Return the ordered list of checkpoint transitions from start to finish for a thread_id."""
    history = list(graph.get_state_history({"configurable": {"thread_id": thread_id}}))
    transitions: list[dict[str, Any]] = []
    for snapshot in reversed(history):
        cfg = snapshot.config.get("configurable", {})
        meta = snapshot.metadata if isinstance(snapshot.metadata, dict) else {}
        values = dict(snapshot.values) if snapshot.values else {}
        transitions.append({
            "checkpoint_id": cfg.get("checkpoint_id"),
            "step": meta.get("step"),
            "source": meta.get("source"),
            "next": list(snapshot.next) if snapshot.next else [],
            "route": values.get("route"),
            "has_context": bool(values.get("retrieved_context")),
            "has_answer": bool(values.get("answer")),
            "error_code": values.get("error_code"),
        })
    return transitions


def execute_agent_query(
    question: str,
    *,
    run_id: str | None = None,
    thread_id: str | None = None,
    trace_dir: Path | str | None = None,
    checkpointer: Any = None,
    retrieve_fn: Callable[..., list[dict[str, Any]]] = retrieve,
    generate_fn: Callable[..., str] = generate_answer,
    config_fn: Callable[[], Settings] = settings,
) -> dict[str, Any]:
    """Execute the compiled LangGraph agent, record checkpoints, and persist a consultable trace."""
    resolved_run_id = (run_id or f"run-{uuid4().hex[:12]}").strip()
    resolved_thread_id = (thread_id or resolved_run_id).strip()
    started_at = datetime.now(timezone.utc).isoformat()
    steps: list[dict[str, Any]] = []
    nodes_order: list[str] = []

    def record_step(node_name: str, update: dict[str, Any], duration_ms: float) -> None:
        nodes_order.append(node_name)
        summary: dict[str, Any] = {
            "node": node_name,
            "duration_ms": duration_ms,
            "route": update.get("route"),
        }
        if "retrieved_context" in update:
            chunks = update["retrieved_context"] or []
            summary["retrieved_count"] = len(chunks)
            summary["retrieved_sources"] = [
                {
                    "source_document": c["source_document"],
                    "section": c["section"],
                    "chunk_index": c.get("chunk_index", 0),
                }
                for c in chunks
            ]
        if "answer" in update:
            summary["answer_length"] = len(update["answer"] or "")
        if update.get("error_code"):
            summary["error_code"] = update["error_code"]
        steps.append(summary)

    active_checkpointer = checkpointer if checkpointer is not None else DEFAULT_CHECKPOINTER
    graph = build_agent_graph(
        checkpointer=active_checkpointer,
        retrieve_fn=retrieve_fn,
        generate_fn=generate_fn,
        config_fn=config_fn,
        step_observer=record_step,
    )
    run_config = {"configurable": {"thread_id": resolved_thread_id}}

    try:
        final_state: AgentState = graph.invoke(
            {"run_id": resolved_run_id, "question": question},
            config=run_config,
        )
        validate_agent_state(final_state)
        checkpoints = get_run_checkpoints(resolved_thread_id, graph=graph)
        sanitized_context = [
            sanitize_chunk_summary(c) for c in (final_state.get("retrieved_context") or [])
        ]
        if final_state.get("route") == "empty_question" or final_state.get("error_code"):
            trace_payload = {
                "run_id": resolved_run_id,
                "thread_id": resolved_thread_id,
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": "rejected",
                "route": final_state.get("route", "empty_question"),
                "question": final_state.get("question", ""),
                "nodes_order": nodes_order,
                "steps": steps,
                "checkpoints": checkpoints,
                "retrieved_context": sanitized_context,
                "answer": "",
                "error": {
                    "code": final_state.get("error_code") or "INVALID_QUESTION",
                    "message": "La pregunta debe tener entre 1 y 2000 caracteres.",
                },
            }
            save_trace(trace_payload, directory=trace_dir)
            raise InvalidQuestionError("La pregunta no puede estar vacía ni superar 2000 caracteres.")

        trace_payload = {
            "run_id": resolved_run_id,
            "thread_id": resolved_thread_id,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "route": final_state.get("route", "grounded"),
            "question": final_state.get("question", question.strip()),
            "nodes_order": nodes_order,
            "steps": steps,
            "checkpoints": checkpoints,
            "retrieved_context": sanitized_context,
            "answer": final_state.get("answer", ""),
            "error": None,
        }
        save_trace(trace_payload, directory=trace_dir)
        return {
            "run_id": resolved_run_id,
            "thread_id": resolved_thread_id,
            "answer": final_state["answer"],
            "route": final_state["route"],
        }
    except InvalidQuestionError:
        raise
    except Exception as exc:
        code, safe_msg = _classify_error(exc)
        checkpoints = get_run_checkpoints(resolved_thread_id, graph=graph)
        snapshot = get_run_state(resolved_thread_id, graph=graph).get("values", {})
        sanitized_context = [
            sanitize_chunk_summary(c) for c in (snapshot.get("retrieved_context") or [])
        ]
        trace_payload = {
            "run_id": resolved_run_id,
            "thread_id": resolved_thread_id,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "route": snapshot.get("route"),
            "question": snapshot.get("question", question.strip() if isinstance(question, str) else ""),
            "nodes_order": nodes_order,
            "steps": steps,
            "checkpoints": checkpoints,
            "retrieved_context": sanitized_context,
            "answer": None,
            "error": {
                "code": code,
                "message": safe_msg,
            },
        }
        save_trace(trace_payload, directory=trace_dir)
        raise
