"""LangGraph state machine for Brasaland's RAG and incident support agent."""
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
import re
import time
from typing import Any, Literal
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.domains.agent.mcp_client import (
    IncidentToolInput,
    IncidentToolResult,
    IncidentToolStatus,
    query_incidents_via_mcp,
)
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
INCIDENT_SCOPE_PATTERN = re.compile(r"\b(incidencias?|incidentes?|tickets?|reportes?|casos?)\b", re.I)
OPERATIONAL_PATTERN = re.compile(
    r"\b(estado|status|situaci[oó]n|seguimiento|actual|abiert[ao]s?|"
    r"en progreso|resuelt[ao]s?|descartad[ao]s?|cu[aá]nt[oa]s?|listar|lista)\b",
    re.I,
)
POLICY_PATTERN = re.compile(
    r"\b(puntos?|oro|plata|bronce|descuento|pol[ií]ticas?|procedimientos?|"
    r"protocolos?|manual|al[eé]rgenos|proveedor(?:es)?|desperdicio|men[uú])\b",
    re.I,
)
INCIDENT_STATUS_FILTERS = {
    "open": re.compile(r"\b(abiert[ao]s?|open)\b", re.I),
    "in_progress": re.compile(r"\b(en progreso|en curso|proceso)\b", re.I),
    "resolved": re.compile(r"\b(resuelt[ao]s?|cerrad[ao]s?|resolved)\b", re.I),
    "discarded": re.compile(r"\b(descartad[ao]s?|discarded)\b", re.I),
}
INCIDENT_CATEGORY_FILTERS = {
    "CUSTOMER_COMPLAINT": re.compile(r"\b(queja|reclamo)\b", re.I),
    "EQUIPMENT": re.compile(r"\b(equipamiento|equipo)\b", re.I),
    "SUPPLY": re.compile(r"\b(abastecimiento|suministro)\b", re.I),
    "FOOD_QUALITY": re.compile(r"\b(calidad de alimentos|calidad)\b", re.I),
    "STAFF": re.compile(r"\b(personal|empleado)\b", re.I),
}
INCIDENT_ID_FILTER = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{12}(?![A-Za-z0-9])")
SHORT_NUMERIC_REFERENCE = re.compile(r"(?<!\w)\d{1,11}(?!\w)")
INCIDENT_BRANCH_FILTER = re.compile(r"\b(COL-\d{2}|FLA-\d{2}|HQ-MDE)\b", re.I)
TRACE_INCIDENT_ID_PATTERN = INCIDENT_ID_FILTER


def _sanitize_trace_answer(answer: str) -> str:
    return TRACE_INCIDENT_ID_PATTERN.sub("[id redactado]", answer)


class InvalidQuestionError(RagError):
    """Raised when the agent graph rejects an empty or out-of-bounds question."""


def route_after_receive(
    state: AgentState,
) -> Literal["reject_invalid_question", "retrieve_context", "query_incidents", "clarify_incident_reference"]:
    validate_agent_state(state)
    if state.get("route") == "empty_question":
        return "reject_invalid_question"
    source = state.get("source")
    if source == "clarification":
        return "clarify_incident_reference"
    if source == "incidents":
        return "query_incidents"
    return "retrieve_context"


def route_after_retrieve(
    state: AgentState,
) -> Literal["generate_grounded_answer", "abstain_without_evidence"]:
    validate_agent_state(state)
    context = state.get("retrieved_context") or []
    if len(context) > 0 and state.get("route") == "grounded":
        return "generate_grounded_answer"
    return "abstain_without_evidence"


def route_after_rag_answer(state: AgentState) -> Literal["query_incidents", "__end__"]:
    validate_agent_state(state)
    return "query_incidents" if state.get("source") == "both" else "__end__"


def _decide_sources(
    question: str,
) -> tuple[str, dict[str, str] | None, bool]:
    """Route by operational intent plus incident context, not by a single keyword."""
    incident_ids = INCIDENT_ID_FILTER.findall(question)
    mentions_incident = bool(INCIDENT_SCOPE_PATTERN.search(question))
    asks_operational = bool(OPERATIONAL_PATTERN.search(question))
    operational = (
        asks_operational and (mentions_incident or bool(incident_ids))
    ) or (mentions_incident and bool(incident_ids))
    asks_policy = bool(POLICY_PATTERN.search(question))

    if not operational:
        return "rag", None, False

    query: dict[str, str] = {}
    if incident_ids:
        query["incident_id"] = incident_ids[0]
    else:
        status = next(
            (key for key, pattern in INCIDENT_STATUS_FILTERS.items() if pattern.search(question)),
            None,
        )
        category = next(
            (key for key, pattern in INCIDENT_CATEGORY_FILTERS.items() if pattern.search(question)),
            None,
        )
        branch_match = INCIDENT_BRANCH_FILTER.search(question)
        if status:
            query["status"] = status
        if category:
            query["category"] = category
        if branch_match:
            query["branch"] = branch_match.group(1).upper()
        # Aggregate/list questions can use the incident API's real, unfiltered GET.
        is_aggregate = bool(re.search(r"\b(cu[aá]nt[oa]s?|lista|listar)\b", question, re.I))
        if not query and not is_aggregate:
            return ("both" if asks_policy else "clarification"), None, True
        if SHORT_NUMERIC_REFERENCE.search(question):
            return ("both" if asks_policy else "clarification"), None, True

    return ("both" if asks_policy else "incidents"), query, False


def route_after_incident_query(state: AgentState) -> Literal["compose_incident_answer"]:
    validate_agent_state(state)
    return "compose_incident_answer"


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
    generate_fn: Callable[..., Any] = generate_answer,
    config_fn: Callable[[], Settings] = settings,
    incident_fn: Callable[[IncidentToolInput], IncidentToolResult] | None = None,
    memory_read_fn: Callable[[str, str], list[dict[str, Any]]] | None = None,
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
        conversation_id = state.get("conversation_id")
        raw_question = state.get("question")
        cleaned = raw_question.strip() if isinstance(raw_question, str) else ""
        if not cleaned or len(cleaned) > MAX_QUESTION_LENGTH:
            return _observe(
                "receive_question",
                {
                    "run_id": run_id,
                    "question": cleaned,
                    "conversation_id": conversation_id,
                    "retrieved_context": [],
                    "memory_context": [],
                    "memory_candidate": None,
                    "route": "empty_question",
                    "source": "clarification",
                    "error_code": "INVALID_QUESTION",
                },
                started,
            )
        memories: list[dict[str, Any]] = []
        if memory_read_fn is not None:
            try:
                memories = memory_read_fn(conversation_id or "", cleaned) or []
            except Exception:
                memories = []
        source, incident_query, incident_clarification = _decide_sources(cleaned)
        return _observe(
            "receive_question",
            {
                "run_id": run_id,
                "question": cleaned,
                "conversation_id": conversation_id,
                "retrieved_context": [],
                "memory_context": memories,
                "memory_candidate": None,
                "route": "valid",
                "source": source,
                "incident_query": incident_query or {},
                "incident_clarification": incident_clarification,
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
                "source": state.get("source", "clarification"),
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
        memories = state.get("memory_context") or []
        gen_result = generate_fn(state["question"], context, memories=memories, config=cfg)
        if isinstance(gen_result, tuple):
            answer, candidate = gen_result
        else:
            answer, candidate = gen_result, None
        return _observe(
            "generate_grounded_answer",
            {
                "answer": answer,
                "rag_answer": answer,
                "route": "grounded",
                "error_code": None,
                "memory_candidate": candidate,
            },
            started,
        )

    def abstain_without_evidence(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        cfg = config_fn()
        memories = state.get("memory_context") or []
        gen_result = generate_fn(state["question"], [], memories=memories, config=cfg)
        if isinstance(gen_result, tuple):
            answer, candidate = gen_result
        else:
            answer, candidate = gen_result, None
        return _observe(
            "abstain_without_evidence",
            {
                "answer": answer,
                "rag_answer": answer,
                "route": "no_evidence",
                "error_code": None,
                "memory_candidate": candidate,
            },
            started,
        )

    def clarify_incident_reference(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        return _observe(
            "clarify_incident_reference",
            {
                "answer": (
                    "Para consultar una incidencia necesito su ID interno de 12 caracteres "
                    "hexadecimales. El número indicado no identifica inequívocamente una "
                    "incidencia; no puedo buscarlo como referencia externa."
                ),
                "route": "clarification",
                "fallback": False,
            },
            started,
        )

    def query_incident_manager(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        if state.get("incident_clarification"):
            result = IncidentToolResult(
                status=IncidentToolStatus.AMBIGUOUS,
                message=(
                    "Para consultar la incidencia necesito su ID interno de 12 caracteres "
                    "hexadecimales. No puedo buscar el número indicado como referencia externa."
                ),
            )
        else:
            query = IncidentToolInput.model_validate(state.get("incident_query", {}))
            result = incident_fn(query) if incident_fn is not None else query_incidents_via_mcp(query)
        return _observe(
            "query_incidents",
            {
                "incident_result": result.model_dump(mode="json"),
                "fallback": result.status not in {
                    IncidentToolStatus.SUCCESS,
                    IncidentToolStatus.AMBIGUOUS,
                },
            },
            started,
        )

    def compose_incident_answer(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        validate_agent_state(state)
        result = IncidentToolResult.model_validate(state["incident_result"])
        if result.status == IncidentToolStatus.SUCCESS:
            if result.incidents:
                rows = [
                    (
                        f"ID: {item.id}; estado: {item.status}; categoría: {item.category}; "
                        f"sucursal: {item.branch}; última actualización: {item.updated_at}; "
                        f"origen: {item.origin}."
                    )
                    for item in result.incidents
                ]
                incident_answer = "\n".join(rows)
            else:
                incident_answer = "El gestor no encontró incidencias que coincidan con esos filtros."
            fallback = False
        else:
            incident_answer = result.message
            fallback = result.status != IncidentToolStatus.AMBIGUOUS

        if state.get("source") == "both":
            answer = (
                f"Información de políticas/documentación:\n{state.get('rag_answer', '')}\n\n"
                f"Datos actuales de incidencias:\n{incident_answer}"
            )
            route = "both"
        else:
            answer = incident_answer
            route = "fallback" if fallback else "incidents"
        return _observe(
            "compose_incident_answer",
            {"answer": answer, "route": route, "fallback": fallback},
            started,
        )

    workflow = StateGraph(AgentState)
    workflow.add_node("receive_question", receive_question)
    workflow.add_node("reject_invalid_question", reject_invalid_question)
    workflow.add_node("retrieve_context", retrieve_context)
    workflow.add_node("generate_grounded_answer", generate_grounded_answer)
    workflow.add_node("abstain_without_evidence", abstain_without_evidence)
    workflow.add_node("clarify_incident_reference", clarify_incident_reference)
    workflow.add_node("query_incidents", query_incident_manager)
    workflow.add_node("compose_incident_answer", compose_incident_answer)

    workflow.add_edge(START, "receive_question")
    workflow.add_conditional_edges(
        "receive_question",
        route_after_receive,
        {
            "reject_invalid_question": "reject_invalid_question",
            "retrieve_context": "retrieve_context",
            "query_incidents": "query_incidents",
            "clarify_incident_reference": "clarify_incident_reference",
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
    workflow.add_conditional_edges(
        "generate_grounded_answer",
        route_after_rag_answer,
        {"query_incidents": "query_incidents", "__end__": END},
    )
    workflow.add_conditional_edges(
        "abstain_without_evidence",
        route_after_rag_answer,
        {"query_incidents": "query_incidents", "__end__": END},
    )
    workflow.add_conditional_edges(
        "query_incidents",
        route_after_incident_query,
        {"compose_incident_answer": "compose_incident_answer"},
    )
    workflow.add_edge("compose_incident_answer", END)
    workflow.add_edge("clarify_incident_reference", END)

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
    conversation_id: str | None = None,
    user_uuid: str | None = None,
    memory_policy: Any = None,
    trace_dir: Path | str | None = None,
    checkpointer: Any = None,
    retrieve_fn: Callable[..., list[dict[str, Any]]] = retrieve,
    generate_fn: Callable[..., Any] = generate_answer,
    config_fn: Callable[[], Settings] = settings,
    incident_fn: Callable[[IncidentToolInput], IncidentToolResult] | None = None,
) -> dict[str, Any]:
    """Execute the compiled LangGraph agent, record checkpoints, and persist a consultable trace."""
    resolved_run_id = (run_id or f"run-{uuid4().hex[:12]}").strip()
    resolved_conversation_id = (conversation_id or thread_id or f"conv-{uuid4().hex[:12]}").strip()
    resolved_thread_id = resolved_conversation_id
    started_at = datetime.now(timezone.utc).isoformat()

    from app.domains.agent import memory as agent_memory
    policy = memory_policy
    if policy is None:
        try:
            from app.domains.agent.memory import DEFAULT_POLICY as _DP
            policy = _DP
        except Exception:
            policy = None

    working_question = question
    if user_uuid is not None:
        try:
            pending = agent_memory.get_pending_proposal(resolved_conversation_id, user_uuid)
        except Exception:
            pending = None
        if pending is not None:
            try:
                classification = agent_memory.classify_proposal_response(question, pending)
            except Exception:
                classification = None
            if classification is not None:
                decision = classification.decision
                if decision in {"approve", "reject", "edit"}:
                    try:
                        agent_memory.resolve_proposal(
                            pending.proposal_id,
                            user_uuid,
                            decision,
                            revised_fact=classification.revised_fact,
                            policy=policy,
                            user_uuid=user_uuid,
                        )
                    except Exception:
                        pass
                elif decision == "ambiguous":
                    try:
                        agent_memory.expire_pending(resolved_conversation_id, user_uuid, "ambiguous_or_topic_change", actor_uuid=user_uuid)
                    except Exception:
                        pass
                residual = None
                if decision in {"approve", "reject", "edit"}:
                    residual = classification.new_query
                elif decision == "ambiguous":
                    residual = question
                if residual is None:
                    try:
                        new_pending = agent_memory.get_pending_proposal(resolved_conversation_id, user_uuid)
                    except Exception:
                        new_pending = None
                    if decision == "approve":
                        ack = "He procesado la propuesta de memoria."
                    elif decision == "reject":
                        ack = "Entendido: no guardaré ese recuerdo."
                    elif decision == "edit":
                        if new_pending is not None:
                            ack = f"He creado una propuesta revisada: {new_pending.proposed_fact}. ¿La apruebas?"
                        else:
                            ack = "No pude crear una propuesta revisada válida."
                    else:
                        ack = "No entendí la respuesta a la propuesta pendiente; la he descartado."
                    return {
                        "run_id": resolved_run_id,
                        "thread_id": resolved_thread_id,
                        "conversation_id": resolved_conversation_id,
                        "answer": ack,
                        "route": "memory_proposal_resolved",
                        "memory_proposal": None,
                    }
                working_question = residual

    def _read_memories(conv_id: str, q: str) -> list[dict[str, Any]]:
        if user_uuid is None:
            return []
        try:
            return agent_memory.read_relevant_memories(user_uuid, conv_id, q, policy=policy, limit=5)
        except Exception:
            return []

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
        if "source" in update:
            summary["source"] = update["source"]
        if "incident_result" in update:
            summary["incident_result"] = update["incident_result"]["status"]
        if "fallback" in update:
            summary["fallback"] = update["fallback"]
        steps.append(summary)

    active_checkpointer = checkpointer if checkpointer is not None else DEFAULT_CHECKPOINTER
    graph = build_agent_graph(
        checkpointer=active_checkpointer,
        retrieve_fn=retrieve_fn,
        generate_fn=generate_fn,
        config_fn=config_fn,
        incident_fn=incident_fn or (
            lambda query: query_incidents_via_mcp(query)
        ),
        memory_read_fn=_read_memories,
        step_observer=record_step,
    )
    run_config = {"configurable": {"thread_id": resolved_thread_id}}

    try:
        final_state: AgentState = graph.invoke(
            {"run_id": resolved_run_id, "question": working_question, "conversation_id": resolved_conversation_id, "memory_context": _read_memories(resolved_conversation_id, working_question) if user_uuid is not None else []},
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
                "question_length": len(final_state.get("question", "")),
                "source": final_state.get("source"),
                "incident_tool_result": None,
                "fallback": bool(final_state.get("fallback", False)),
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
            "question_length": len(final_state.get("question", working_question.strip())),
            "source": final_state.get("source"),
            "incident_tool_result": (
                final_state.get("incident_result", {}).get("status")
            ),
            "fallback": bool(final_state.get("fallback", False)),
            "nodes_order": nodes_order,
            "steps": steps,
            "checkpoints": checkpoints,
            "retrieved_context": sanitized_context,
            "answer": _sanitize_trace_answer(final_state.get("answer", "")),
            "error": None,
        }
        save_trace(trace_payload, directory=trace_dir)
        memory_proposal = None
        memory_candidate = final_state.get("memory_candidate")
        if user_uuid is not None and memory_candidate is not None:
            try:
                proposal = agent_memory.propose_memory(
                    user_uuid,
                    resolved_conversation_id,
                    resolved_run_id,
                    memory_candidate,
                    policy=policy,
                )
                if proposal is not None:
                    memory_proposal = {
                        "proposal_id": proposal.proposal_id,
                        "fact": proposal.proposed_fact,
                        "category": proposal.category,
                        "rationale": proposal.rationale,
                        "confidence": proposal.confidence,
                        "status": proposal.status,
                        "expires_at": proposal.expires_at,
                    }
            except Exception:
                memory_proposal = None
        return {
            "run_id": resolved_run_id,
            "thread_id": resolved_thread_id,
            "conversation_id": resolved_conversation_id,
            "answer": final_state["answer"],
            "route": final_state["route"],
            "memory_proposal": memory_proposal,
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
            "question_length": len(snapshot.get(
                "question", working_question.strip() if isinstance(working_question, str) else ""
            )),
            "source": snapshot.get("source"),
            "incident_tool_result": snapshot.get("incident_result", {}).get("status"),
            "fallback": bool(snapshot.get("fallback", False)),
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
