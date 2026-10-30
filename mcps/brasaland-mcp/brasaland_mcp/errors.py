"""Tool result envelope and backend error classification.

Every tool returns a structured envelope so clients (and the agent) can
distinguish outcomes by code without parsing prose:

    success            operation completed, `data` carries the payload
    validation_error   input rejected by the Brasaland backend (field-level)
    not_found          incident/product does not exist
    invalid_transition state-machine rejection from the incidents lifecycle
    duplicate          incident already exists (409)
    insufficient_scope valid OAuth token lacks the scope for this tool
    write_not_supported inventory modification attempted against a read-only server
    backend_timeout    Brasaland API exceeded the configured timeout
    backend_unavailable Brasaland API unreachable or returned 5xx
    internal_error     unexpected server-side failure (details never exposed)

Transport-level authentication failures (missing/invalid/expired token, bad
signature/issuer/audience) never reach a tool: `mcpauth` rejects them with
HTTP 401 + `WWW-Authenticate` before the MCP session exists.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class ToolStatus(StrEnum):
    SUCCESS = "success"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    INVALID_TRANSITION = "invalid_transition"
    DUPLICATE = "duplicate"
    INSUFFICIENT_SCOPE = "insufficient_scope"
    WRITE_NOT_SUPPORTED = "write_not_supported"
    BACKEND_TIMEOUT = "backend_timeout"
    BACKEND_UNAVAILABLE = "backend_unavailable"
    INTERNAL_ERROR = "internal_error"


def ok(data: Any, message: str, *, correlation_id: str) -> dict[str, Any]:
    """Success envelope."""
    return {
        "status": ToolStatus.SUCCESS.value,
        "message": message,
        "data": data,
        "correlation_id": correlation_id,
    }


def fail(
    status: ToolStatus,
    message: str,
    *,
    correlation_id: str,
    field: str | None = None,
) -> dict[str, Any]:
    """Error envelope; distinct `status` codes per failure class."""
    envelope: dict[str, Any] = {
        "status": status.value,
        "message": message,
        "correlation_id": correlation_id,
    }
    if field is not None:
        envelope["field"] = field
    return envelope


def classify_backend_error(
    status_code: int,
    body: Any,
    *,
    endpoint: str,
) -> tuple[ToolStatus, str, str | None]:
    """Map a Brasaland API error response onto a ToolStatus.

    Uses only what the backend already decided (HTTP code plus the
    `IncidentErrorResponse` fields `message`/`field`); business rules are never
    re-implemented here. Returns (status, message, field).
    """
    message = "El backend de Brasaland devolvió un error."
    field: str | None = None
    if isinstance(body, dict):
        raw_message = body.get("message") or body.get("detail")
        if isinstance(raw_message, str) and raw_message:
            message = raw_message
        raw_field = body.get("field")
        if isinstance(raw_field, str) and raw_field:
            field = raw_field

    if status_code == 404:
        return ToolStatus.NOT_FOUND, message, field
    if status_code == 409:
        return ToolStatus.DUPLICATE, message, field
    if status_code in {401, 403}:
        # The MCP service account lost access to the backend: an availability
        # problem from the client's perspective, never a credential leak.
        return (
            ToolStatus.BACKEND_UNAVAILABLE,
            "El backend de Brasaland rechazó la credencial del servicio MCP.",
            None,
        )
    if status_code == 422:
        return ToolStatus.VALIDATION_ERROR, message, field
    if status_code == 400:
        if endpoint == "status" and field is None:
            # IncidentInvalidTransitionError: terminal state rejection.
            return ToolStatus.INVALID_TRANSITION, message, field
        if endpoint == "status" and "Cannot transition" in message:
            return ToolStatus.INVALID_TRANSITION, message, field
        return ToolStatus.VALIDATION_ERROR, message, field
    return (
        ToolStatus.BACKEND_UNAVAILABLE,
        "El backend de Brasaland no está disponible en este momento.",
        None,
    )
