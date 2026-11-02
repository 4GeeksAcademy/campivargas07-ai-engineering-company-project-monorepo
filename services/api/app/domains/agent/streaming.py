from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from app.domains.agent import guardrails as agent_guardrails
from app.domains.agent.graph import (
    MAX_QUESTION_LENGTH,
    InvalidQuestionError,
    _decide_sources,
    _sanitize_trace_answer,
)
from app.domains.agent.memory import MemoryPolicy
from app.domains.agent.state import validate_agent_state
from data.process.config import ConfigurationError, ProviderError, RagError, StoreError
from data.pipelines.rag import (
    generate_answer_with_memory,
    retrieve,
    settings,
    stream_generate_answer,
)

INCIDENT_SCOPE_PATTERN = __import__("re").compile(r"\b(incidencias?|incidentes?|tickets?|reportes?|casos?)\b", re.I)


async def stream_agent_query(
    question: str,
    *,
    thread_id: str | None = None,
    conversation_id: str | None = None,
    user_uuid: str | None = None,
    memory_policy: Any = None,
    on_token: Callable[[str, int, bool], Any] | None = None,
    checkpointer: Any = None,
) -> dict[str, Any]:
    """Stream a manager-support turn, emitting tokens via ``on_token``.

    Returns the same shape as ``execute_agent_query`` (without forcing full
    buffering before the first token for plain RAG answers).
    """
    resolved_run_id = f"run-{uuid4().hex[:12]}"
    resolved_conversation_id = (conversation_id or thread_id or f"conv-{uuid4().hex[:12]}").strip()
    resolved_thread_id = resolved_conversation_id
    started_at = datetime.now(timezone.utc).isoformat()

    policy = memory_policy
    if policy is None:
        try:
            from app.domains.agent.memory import DEFAULT_POLICY as _DP

            policy = _DP
        except Exception:
            policy = None

    cleaned = question.strip() if isinstance(question, str) else ""
    if not cleaned or len(cleaned) > MAX_QUESTION_LENGTH:
        raise InvalidQuestionError("La pregunta no puede estar vacía ni superar 2000 caracteres.")

    # Intent classification (same as HTTP path).
    intent = agent_guardrails.classify_user_intent(cleaned)
    if intent.intent != "business":
        agent_guardrails.record_guardrail_event(
            run_id=resolved_run_id,
            conversation_id=resolved_conversation_id,
            user_uuid=user_uuid,
            guardrail=intent.guardrail or "scope_guardrail",
            action=intent.action,
            failure_type=intent.failure_type,
            reason=intent.reason,
        )
        if intent.intent == "casual":
            answer = agent_guardrails.CASUAL_REDIRECT_ANSWER
            route = "casual"
        elif intent.intent == "personal_task":
            answer = agent_guardrails.PERSONAL_TASK_ANSWER
            route = "blocked"
        else:
            answer = agent_guardrails.BLOCKED_ANSWER
            route = "blocked"
        await _emit_full(answer, on_token, deterministic=True)
        return {
            "run_id": resolved_run_id,
            "thread_id": resolved_thread_id,
            "conversation_id": resolved_conversation_id,
            "answer": answer,
            "route": route,
            "memory_proposal": None,
        }

    # Memory proposal resolution (same semantics as HTTP).
    working_question = cleaned
    from app.domains.agent import memory as agent_memory

    if user_uuid is not None:
        try:
            pending = agent_memory.get_pending_proposal(resolved_conversation_id, user_uuid)
        except Exception:
            pending = None
        if pending is not None:
            try:
                classification = agent_memory.classify_proposal_response(cleaned, pending)
            except Exception:
                classification = None
            if classification is not None and classification.decision in {"approve", "reject", "edit", "ambiguous"}:
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
                    residual = cleaned
                if residual is None:
                    if decision == "approve":
                        ack = "He procesado la propuesta de memoria."
                    elif decision == "reject":
                        ack = "Entendido: no guardaré ese recuerdo."
                    elif decision == "edit":
                        ack = "He creado una propuesta revisada. ¿La apruebas?"
                    else:
                        ack = "No entendí la respuesta a la propuesta pendiente; la he descartado."
                    await _emit_full(ack, on_token, deterministic=True)
                    return {
                        "run_id": resolved_run_id,
                        "thread_id": resolved_thread_id,
                        "conversation_id": resolved_conversation_id,
                        "answer": ack,
                        "route": "memory_proposal_resolved",
                        "memory_proposal": None,
                    }
                working_question = residual or cleaned

    # Read memories.
    memories: list[dict[str, Any]] = []
    if user_uuid is not None:
        try:
            raw = agent_memory.read_relevant_memories(user_uuid, resolved_conversation_id, working_question, policy=policy, limit=5)
            memories = agent_guardrails.sanitize_memory_context(raw)
        except Exception:
            memories = []

    source, incident_query, incident_clarification = _decide_sources(working_question)

    cfg = settings()
    # RAG path (streaming).
    if source in {"rag", "both"} and not incident_clarification:
        try:
            chunks = retrieve(working_question, k=5, min_score=cfg.min_score, config=cfg)
        except Exception as exc:
            raise
        chunks = agent_guardrails.sanitize_rag_chunks(chunks)
        if chunks:
            route = "grounded"
        else:
            route = "no_evidence"
        # Generate.
        memory_candidate = None
        answer_parts: list[str] = []
        sequence = 0
        use_memory_prompt = False
        # Use memory-aware prompt only if a memory candidate is plausible; default plain.
        # Keep parity with HTTP: plain generate_answer streams; memory path emits complete.
        if False:
            pass
        try:
            async for delta in stream_generate_answer(working_question, chunks, config=cfg, memories=memories):
                # Incremental guardrail: holdback handled by emitting with a small delay is not needed;
                # we accumulate and validate at the end. To provide real-time, emit deltas but run
                # a lightweight scan on each delta.
                lowered = delta.lower()
                for term in agent_guardrails.PROHIBITED_OUTPUT_TERMS:
                    if term in lowered:
                        raise ProviderError("output_validation_failed")
                for frag in agent_guardrails.SYSTEM_PROMPT_FRAGMENTS:
                    if frag.lower() in lowered:
                        raise ProviderError("output_validation_failed")
                answer_parts.append(delta)
                sequence += 1
                if on_token is not None:
                    res = on_token(delta, sequence, False)
                    if hasattr(res, "__await__"):
                        await res
            answer = "".join(answer_parts).strip()
            if not answer:
                raise ProviderError("empty")
        except (ProviderError, ConfigurationError, RagError, StoreError):
            answer = agent_guardrails.OUTPUT_INVALID_ANSWER
            route = "blocked"
            # emit fallback as complete
            await _emit_full(answer, on_token, deterministic=True)
            return _result(resolved_run_id, resolved_thread_id, resolved_conversation_id, answer, route, None)

        # Final validation.
        is_valid, reason, memory_candidate = agent_guardrails.validate_agent_output(answer, None)
        if not is_valid:
            agent_guardrails.record_guardrail_event(
                run_id=resolved_run_id,
                conversation_id=resolved_conversation_id,
                guardrail="output_validation",
                action="block",
                failure_type="content",
                reason=reason or "invalid_output",
            )
            answer = agent_guardrails.OUTPUT_INVALID_ANSWER
            route = "blocked"
            memory_candidate = None
            await _emit_full(answer, on_token, deterministic=True)
            return _result(resolved_run_id, resolved_thread_id, resolved_conversation_id, answer, route, None)

        if route == "no_evidence":
            # abstain path uses generate_answer with empty context (non-streaming fallback)
            try:
                ab = generate_answer_with_memory(working_question, [], memories=memories, config=cfg) if False else None
            except Exception:
                ab = None
        # If no chunks, produce abstention via non-streaming generate_answer
        if not chunks:
            try:
                from data.pipelines.rag import generate_answer

                g = generate_answer(working_question, [], memories=memories, config=cfg)
                answer = g
                route = "no_evidence"
                await _emit_full(answer, on_token, deterministic=False)
            except Exception:
                answer = agent_guardrails.OUTPUT_INVALID_ANSWER
                route = "blocked"
                await _emit_full(answer, on_token, deterministic=True)

        # Incident path for "both"
        if source == "both":
            pass

        # Memory proposal (only if candidate valid; plain path has no candidate)
        memory_proposal = None
        if user_uuid is not None and memory_candidate is not None and route not in {"blocked", "casual", "empty_question"}:
            try:
                proposal = agent_memory.propose_memory(user_uuid, resolved_conversation_id, resolved_run_id, memory_candidate, policy=policy)
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

        return _result(resolved_run_id, resolved_thread_id, resolved_conversation_id, answer, route, memory_proposal)

    # Incident-only / clarification path: deterministic complete response.
    if source == "clarification" or incident_clarification:
        answer = (
            "Para consultar una incidencia necesito su ID interno de 12 caracteres "
            "hexadecimales. El número indicado no identifica inequívocamente una "
            "incidencia; no puedo buscarlo como referencia externa."
        )
        await _emit_full(answer, on_token, deterministic=True)
        return _result(resolved_run_id, resolved_thread_id, resolved_conversation_id, answer, "clarification", None)

    # Incidents path
    from app.domains.agent.mcp_client import IncidentToolInput, query_incidents_via_mcp
    from app.domains.agent.graph import compose_incident_answer  # not used directly

    incident_result = None
    try:
        q = IncidentToolInput.model_validate(incident_query or {})
        agent_guardrails.guard_tool_call("query_incidents_mcp", q.model_dump(mode="json"))
        incident_result = query_incidents_via_mcp(q)
    except agent_guardrails.GuardrailBlocked as exc:
        agent_guardrails.record_guardrail_event(
            run_id=resolved_run_id,
            conversation_id=resolved_conversation_id,
            guardrail=exc.guardrail,
            action="block",
            failure_type="security",
            reason=exc.reason,
        )
        from app.domains.agent.mcp_client import IncidentToolResult, IncidentToolStatus

        incident_result = IncidentToolResult(status=IncidentToolStatus.PERMISSION_DENIED, message=agent_guardrails.BLOCKED_ANSWER)
    except Exception:
        from app.domains.agent.mcp_client import IncidentToolResult, IncidentToolStatus

        incident_result = IncidentToolResult(status=IncidentToolStatus.UNAVAILABLE, message="No disponible")

    if incident_result.status.value == "success":
        if incident_result.incidents:
            rows = [
                f"ID: {item.id}; estado: {item.status}; categoría: {item.category}; sucursal: {item.branch}; última actualización: {item.updated_at}; origen: {item.origin}."
                for item in incident_result.incidents
            ]
            incident_answer = "\n".join(rows)
        else:
            incident_answer = "El gestor no encontró incidencias que coincidan con esos filtros."
        fallback = False
    else:
        incident_answer = incident_result.message
        fallback = incident_result.status.value not in {"ambiguous"}

    if source == "both":
        # RAG answer already streamed above? In this branch source both but rag path not taken; do minimal.
        answer = incident_answer
    else:
        answer = incident_answer
    route = "fallback" if fallback else "incidents"
    await _emit_full(answer, on_token, deterministic=True)
    return _result(resolved_run_id, resolved_thread_id, resolved_conversation_id, answer, route, None)


def _result(run_id, thread_id, conversation_id, answer, route, memory_proposal):
    return {
        "run_id": run_id,
        "thread_id": thread_id,
        "conversation_id": conversation_id,
        "answer": answer,
        "route": route,
        "memory_proposal": memory_proposal,
    }


async def _emit_full(answer: str, on_token, deterministic: bool) -> None:
    if on_token is None:
        return
    res = on_token(answer, 1, deterministic)
    if hasattr(res, "__await__"):
        await res