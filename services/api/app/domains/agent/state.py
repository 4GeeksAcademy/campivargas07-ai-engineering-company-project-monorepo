"""Minimal, typed state for the Brasaland support agent graph (Part 1)."""
from collections.abc import Mapping
from typing import Any, Literal, TypedDict

RouteLiteral = Literal["valid", "empty_question", "grounded", "no_evidence"]

ALLOWED_ROUTES: frozenset[str] = frozenset({"valid", "empty_question", "grounded", "no_evidence"})
ALLOWED_STATE_KEYS: frozenset[str] = frozenset({
    "run_id",
    "question",
    "retrieved_context",
    "answer",
    "route",
    "error_code",
})
FORBIDDEN_STATE_KEYS: frozenset[str] = frozenset({
    "messages",
    "history",
    "conversation_history",
    "api_key",
    "embedding_key",
    "generation_key",
    "qdrant_key",
    "token",
    "access_token",
    "authorization",
    "password",
    "secret",
    "client",
    "http_client",
    "store",
    "user",
    "user_id",
})
REQUIRED_CHUNK_KEYS: frozenset[str] = frozenset({"source_document", "section", "text"})


class StateValidationError(ValueError):
    """Raised when an AgentState payload violates the minimal typed contract."""


class AgentState(TypedDict, total=False):
    """Explicit minimal state carried across LangGraph nodes.

    Contains only the current question, retrieved knowledge chunks, final answer,
    and routing/run metadata. Never stores conversation history, credentials, or HTTP clients.
    """

    run_id: str
    question: str
    retrieved_context: list[dict[str, Any]]
    answer: str
    route: RouteLiteral
    error_code: str | None


def validate_agent_state(state: Mapping[str, Any]) -> AgentState:
    """Validate structural and type invariants that LangGraph compile() alone does not enforce."""
    if not isinstance(state, Mapping):
        raise StateValidationError("El estado del agente debe ser un mapeo.")

    forbidden = set(state.keys()) & FORBIDDEN_STATE_KEYS
    if forbidden:
        raise StateValidationError(
            f"El estado incluye claves prohibidas (historial, credenciales o clientes): {sorted(forbidden)}"
        )

    unknown = set(state.keys()) - ALLOWED_STATE_KEYS
    if unknown:
        raise StateValidationError(f"El estado incluye claves no declaradas: {sorted(unknown)}")

    if "run_id" in state:
        run_id = state["run_id"]
        if not isinstance(run_id, str) or not run_id.strip():
            raise StateValidationError("run_id debe ser un string no vacío.")

    if "question" in state:
        if not isinstance(state["question"], str):
            raise StateValidationError("question debe ser de tipo str.")

    if "retrieved_context" in state:
        ctx = state["retrieved_context"]
        if not isinstance(ctx, list):
            raise StateValidationError("retrieved_context debe ser una lista de chunks.")
        for idx, chunk in enumerate(ctx):
            if not isinstance(chunk, Mapping):
                raise StateValidationError(f"Chunk en posición {idx} debe ser un diccionario.")
            missing = REQUIRED_CHUNK_KEYS - set(chunk.keys())
            if missing:
                raise StateValidationError(
                    f"Chunk en posición {idx} no contiene las claves requeridas: {sorted(missing)}"
                )
            for key in REQUIRED_CHUNK_KEYS:
                if not isinstance(chunk[key], str) or not chunk[key].strip():
                    raise StateValidationError(f"El campo '{key}' del chunk {idx} debe ser texto no vacío.")

    if "answer" in state:
        if not isinstance(state["answer"], str):
            raise StateValidationError("answer debe ser de tipo str.")

    if "route" in state:
        if state["route"] not in ALLOWED_ROUTES:
            raise StateValidationError(f"route inválido: {state['route']!r}")

    if "error_code" in state and state["error_code"] is not None:
        if not isinstance(state["error_code"], str) or not state["error_code"].strip():
            raise StateValidationError("error_code debe ser None o un código string no vacío.")

    return dict(state)  # type: ignore[return-value]
