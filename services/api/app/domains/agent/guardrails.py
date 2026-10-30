"""Harness and guardrails for the Brasaland support agent.

These defenses are deliberately layered: input intent classification, tool-scope
control, external-content isolation, output validation, memory protection and
auditable event recording. None of them relies solely on the system prompt or on
a prohibited-word list, and none of them blocks ordinary business questions.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

logger = logging.getLogger("brasaland.guardrails")

_GUARDRAIL_LOCK = threading.RLock()
_GUARDRAIL_EVENTS: list[dict[str, Any]] = []

MAX_EXTERNAL_TEXT_LENGTH = 4000

CASUAL_REDIRECT_ANSWER = (
    "Soy el agente de soporte de Brasaland para gerentes de local. "
    "Puedo ayudarte con incidencias, inventario o manuales operativos. "
    "¿En qué tema de Brasaland puedo ayudarte?"
)
PERSONAL_TASK_ANSWER = (
    "No puedo realizar tareas personales ajenas al negocio. "
    "Puedo ayudarte con incidencias, inventario o manuales de Brasaland. "
    "¿Qué necesitas?"
)
BLOCKED_ANSWER = (
    "No puedo cambiar mis instrucciones ni revelar información interna. "
    "Puedo ayudarte con consultas operativas de Brasaland. "
    "¿Qué necesitas?"
)
OUTPUT_INVALID_ANSWER = (
    "No puedo generar una respuesta válida con la información disponible. "
    "Puedo ayudarte con incidencias, inventario o manuales de Brasaland."
)
MAX_OUTPUT_LENGTH = 10000


class GuardrailBlocked(Exception):
    """Raised when a tool call is outside the authorized read-only scope."""

    def __init__(self, guardrail: str, reason: str):
        super().__init__(reason)
        self.guardrail = guardrail
        self.reason = reason


@dataclass
class IntentDecision:
    intent: str  # business | casual | personal_task | instruction_override
    guardrail: str | None
    action: str  # allow | redirect | block
    failure_type: str | None  # structural | content | security | None
    reason: str


BUSINESS_INDICATORS = re.compile(
    r"\b(puntos?|oro|plata|bronce|descuento|pol[ií]ticas?|procedimientos?|"
    r"protocolos?|manual|al[eé]rgenos?|proveedor(?:es)?|desperdicio|men[uú]|"
    r"incidencias?|incidentes?|tickets?|reportes?|casos?|inventario|stock|"
    r"producto|local|sucursal|ventas?|sales?|location|brass?aland)\b",
    re.I,
)

JAILBREAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignor\w*.*(instrucc|reglas|prompt)", re.I),
    re.compile(r"(instrucciones?|reglas?|prompt).*(internas|sistema|anteriores|previas)", re.I),
    re.compile(r"act[uú]a\s+como|pretend\w*\s+to\s+be|roleplay", re.I),
    re.compile(r"sin\s+restricciones", re.I),
    re.compile(r"(mu[eé]stra|revela|muestra|print|show|display|leak).*(prompt|reglas|instrucc)", re.I),
    re.compile(r"developer\s+mode|jailbreak|bypass", re.I),
)

PERSONAL_TASK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"traduc\w*|translate\b|email|correo|\bcv\b|resume|homework|tarea|impuestos|taxes", re.I),
    re.compile(r"for my friend|mi amigo|mi amiga|ay[uú]dame con|help me with my", re.I),
    re.compile(r"write (me )?an? (email|essay|poem|story)|escribe (un|una) (correo|ensayo|poema|historia)", re.I),
)

CASUAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(hola|hello|hi|hey|buenos|buenas|gracias|thanks|thank you)\b", re.I),
    re.compile(r"\b(c[oó]mo est[aá]s|qu[eé] tal|what'?s up|how are you)\b", re.I),
    re.compile(r"\b(tell me a joke|chiste|weather|clima|who are you|qu[eé] puedes hacer|what can you do)\b", re.I),
)

OVERRIDE_PHRASES = re.compile(
    r"ignor\w*.*(instrucc|reglas|prompt)|"
    r"(instrucciones?|reglas?|prompt).*(internas|sistema|anteriores|previas)|"
    r"act[uú]a\s+como|sin\s+restricciones|developer\s+mode|jailbreak|bypass",
    re.I,
)

PROHIBITED_OUTPUT_TERMS: tuple[str, ...] = (
    "email", "correo", "telefono", "teléfono", "phone", "direccion", "dirección",
    "address", "nomina", "nómina", "payroll", "salario", "salary",
    "compensacion", "compensación", "compensation", "sueldo",
)

SYSTEM_PROMPT_FRAGMENTS: tuple[str, ...] = (
    "Eres un vendedor entrenado",
    "Usa exclusivamente los hechos",
    "No uses búsqueda web",
    "Conserva exactamente cifras",
)

ALLOWED_EXTERNAL_KEYS = frozenset(
    {"company", "source_document", "section", "language", "chunk_index", "text"}
)
REQUIRED_CHUNK_KEYS = frozenset({"source_document", "section", "text"})

ALLOWED_AGENT_TOOLS = frozenset({"retrieve_knowledge", "query_incidents_mcp", "read_memory"})


def classify_user_intent(question: str) -> IntentDecision:
    text = (question or "").strip()
    if not text:
        return IntentDecision("business", "input_validation", "allow", "structural", "empty input handled by graph")

    # Security-sensitive overrides take precedence over any business wording.
    if any(pattern.search(text) for pattern in JAILBREAK_PATTERNS):
        return IntentDecision(
            "instruction_override",
            "input_guardrail",
            "block",
            "security",
            "attempt to change instructions, identity or restrictions",
        )

    if BUSINESS_INDICATORS.search(text):
        return IntentDecision("business", None, "allow", None, "business question")

    if any(pattern.search(text) for pattern in PERSONAL_TASK_PATTERNS):
        return IntentDecision(
            "personal_task",
            "scope_guardrail",
            "block",
            "content",
            "personal task outside Brasaland business scope",
        )

    if any(pattern.search(text) for pattern in CASUAL_PATTERNS) or len(text.split()) <= 8:
        return IntentDecision(
            "casual",
            "scope_guardrail",
            "redirect",
            "content",
            "casual or general-knowledge conversation",
        )

    # Non-business, non-casual input defaults to a safe redirect rather than
    # executing tools or memory operations.
    return IntentDecision(
        "casual",
        "scope_guardrail",
        "redirect",
        "content",
        "not a recognizable Brasaland business question",
    )


def sanitize_external_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = OVERRIDE_PHRASES.sub("[contenido no confiable]", cleaned)
    return cleaned[:MAX_EXTERNAL_TEXT_LENGTH]


def sanitize_rag_chunks(chunks: Any) -> list[dict[str, Any]]:
    if not isinstance(chunks, list):
        return []
    result: list[dict[str, Any]] = []
    for chunk in chunks:
        if not isinstance(chunk, Mapping):
            continue
        clean: dict[str, Any] = {}
        for key, value in chunk.items():
            if key not in ALLOWED_EXTERNAL_KEYS:
                continue
            if key == "chunk_index":
                if isinstance(value, int) and not isinstance(value, bool):
                    clean[key] = value
                continue
            if key == "text":
                text = sanitize_external_text(value)
                if text:
                    clean[key] = text
            else:
                text = sanitize_external_text(value)
                if text:
                    clean[key] = text
        if not REQUIRED_CHUNK_KEYS.issubset(clean):
            continue
        result.append(clean)
    return result


def sanitize_memory_context(memories: Any) -> list[dict[str, Any]]:
    if not isinstance(memories, list):
        return []
    result: list[dict[str, Any]] = []
    for item in memories:
        if not isinstance(item, Mapping):
            continue
        fact = sanitize_external_text(item.get("fact"))
        if not fact:
            continue
        clean = {
            "memory_id": sanitize_external_text(item.get("memory_id")),
            "category": sanitize_external_text(item.get("category")),
            "fact": fact,
            "source": "agent-memory",
        }
        result.append(clean)
    return result


def sanitize_incident_result(result: Any) -> Any:
    if not isinstance(result, Mapping):
        return result
    clean = dict(result)
    for key, value in list(clean.items()):
        if isinstance(value, str):
            clean[key] = sanitize_external_text(value)
        elif isinstance(value, list):
            clean[key] = [
                sanitize_external_text(v) if isinstance(v, str) else v for v in value
            ]
    return clean


def validate_agent_output(
    answer: Any,
    memory_candidate: Any = None,
) -> tuple[bool, str | None, Any]:
    """Return (is_valid, reason, sanitized_candidate)."""
    if not isinstance(answer, str) or not answer.strip():
        return False, "empty_or_invalid_answer", None
    if len(answer) > MAX_OUTPUT_LENGTH:
        return False, "answer_too_long", None

    lowered = answer.lower()
    for fragment in SYSTEM_PROMPT_FRAGMENTS:
        if fragment.lower() in lowered:
            return False, "system_prompt_leakage", None
    for term in PROHIBITED_OUTPUT_TERMS:
        if term in lowered:
            return False, "prohibited_output_term", None
    if re.search(r"\b(sk-[A-Za-z0-9_-]{10,}|api[_ -]?key|bearer\s+[A-Za-z0-9._-]{10,})\b", answer, re.I):
        return False, "secret_leakage", None

    sanitized_candidate = memory_candidate
    if memory_candidate is not None:
        try:
            from app.domains.agent import memory as agent_memory

            policy = getattr(agent_memory, "DEFAULT_POLICY", None)
            validated = agent_memory.validate_memory_candidate(memory_candidate, policy) if policy is not None else None
        except Exception:
            validated = None
        if validated is None:
            sanitized_candidate = None

    return True, None, sanitized_candidate


def guard_tool_call(name: str, arguments: Any = None) -> None:
    if name not in ALLOWED_AGENT_TOOLS:
        raise GuardrailBlocked("tool_scope_guardrail", f"tool not allowed: {name}")
    lowered = str(name).lower()
    if any(token in lowered for token in ("write", "create", "update", "delete", "patch", "post")):
        raise GuardrailBlocked("tool_scope_guardrail", f"write-like tool blocked: {name}")
    if isinstance(arguments, Mapping):
        for key, value in arguments.items():
            if isinstance(value, str) and OVERRIDE_PHRASES.search(value):
                raise GuardrailBlocked("tool_scope_guardrail", "tool argument contains override phrase")


def record_guardrail_event(
    *,
    run_id: str | None = None,
    conversation_id: str | None = None,
    user_uuid: str | None = None,
    guardrail: str,
    action: str,
    failure_type: str | None = None,
    reason: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "conversation_id": conversation_id,
        "user_uuid": user_uuid,
        "guardrail": guardrail,
        "action": action,
        "failure_type": failure_type,
        "reason": reason,
        "metadata": dict(metadata or {}),
    }
    with _GUARDRAIL_LOCK:
        _GUARDRAIL_EVENTS.append(event)
    logger.info(
        "guardrail=%s action=%s failure_type=%s reason=%s",
        guardrail,
        action,
        failure_type,
        reason,
    )
    return event


def reset_guardrail_events() -> None:
    with _GUARDRAIL_LOCK:
        _GUARDRAIL_EVENTS.clear()


def get_guardrail_events() -> list[dict[str, Any]]:
    with _GUARDRAIL_LOCK:
        return [dict(event) for event in _GUARDRAIL_EVENTS]


def summarize_guardrail_events(events: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    source = list(events) if events is not None else get_guardrail_events()
    by_guardrail = Counter(str(e.get("guardrail")) for e in source)
    by_action = Counter(str(e.get("action")) for e in source)
    by_failure = Counter(str(e.get("failure_type")) for e in source if e.get("failure_type"))
    return {
        "total": len(source),
        "by_guardrail": dict(by_guardrail),
        "by_action": dict(by_action),
        "by_failure_type": dict(by_failure),
        "events": [dict(e) for e in source],
    }


def to_dict(event: Any) -> dict[str, Any]:
    if hasattr(event, "__dataclass_fields__"):
        return asdict(event)
    return dict(event)
