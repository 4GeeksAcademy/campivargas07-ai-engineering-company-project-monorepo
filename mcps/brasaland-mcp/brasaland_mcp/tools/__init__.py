"""Shared plumbing for Brasaland MCP tools.

Every tool executes through `execute_tool`, which centralizes:
- per-tool OAuth scope enforcement (least privilege, boundary 1),
- correlation ids and audit logging (client, tool, result — never bodies),
- a single error taxonomy (see `errors.py`),
- conversion of backend/network failures into structured envelopes.

Tools never leak internal details: unexpected exceptions become a generic
`internal_error` envelope and the audit log only records categorical data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from mcpauth import MCPAuth
from mcpauth.types import AuthInfo

from ..audit import InvocationContext
from ..backend import (
    BackendAuthError,
    BackendTimeout,
    BackendUnavailable,
    BrasalandBackend,
    WriteNotAllowedError,
)
from ..errors import ToolStatus, fail

CORRELATION_ID_LENGTH = 12


@dataclass(frozen=True)
class ToolDeps:
    """Dependencies shared by all registered tools."""

    mcp_auth: MCPAuth
    backend: BrasalandBackend


def invocation_context(info: AuthInfo | None, correlation_id: str, tool: str) -> InvocationContext:
    return InvocationContext(
        correlation_id=correlation_id,
        tool=tool,
        client_id=getattr(info, "client_id", None),
        subject=getattr(info, "subject", None),
        scopes=tuple(getattr(info, "scopes", None) or ()),
    )


def execute_tool(
    deps: ToolDeps,
    tool_name: str,
    required_scopes: tuple[str, ...],
    handler: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    """Run a tool body with scope enforcement, auditing and error mapping.

    `handler` receives the correlation id and must return an envelope from
    `errors.ok`/`errors.fail`. Exceptions raised by the backend layer are
    mapped to envelopes; scope failures never reach the backend.
    """
    correlation_id = uuid4().hex[:CORRELATION_ID_LENGTH]
    info = deps.mcp_auth.auth_info
    context = invocation_context(info, correlation_id, tool_name)

    token_scopes = list(getattr(info, "scopes", None) or [])
    missing = [scope for scope in required_scopes if scope not in token_scopes]
    if missing:
        context.record(ToolStatus.INSUFFICIENT_SCOPE.value)
        return fail(
            ToolStatus.INSUFFICIENT_SCOPE,
            "El token OAuth es válido pero no incluye los permisos requeridos por "
            f"esta herramienta: {', '.join(missing)}.",
            correlation_id=correlation_id,
        )

    try:
        result = handler(correlation_id)
    except WriteNotAllowedError:
        result = fail(
            ToolStatus.WRITE_NOT_SUPPORTED,
            "El servidor MCP de Brasaland rechaza explícitamente operaciones de "
            "escritura sobre esta superficie (sólo lectura por diseño).",
            correlation_id=correlation_id,
        )
    except BackendTimeout:
        result = fail(
            ToolStatus.BACKEND_TIMEOUT,
            "La API de Brasaland excedió el tiempo límite; no se confirmó la operación.",
            correlation_id=correlation_id,
        )
    except (BackendUnavailable, BackendAuthError):
        result = fail(
            ToolStatus.BACKEND_UNAVAILABLE,
            "La API de Brasaland no está disponible en este momento.",
            correlation_id=correlation_id,
        )
    except Exception:
        # Never expose internals; the audit log keeps the categorical status.
        result = fail(
            ToolStatus.INTERNAL_ERROR,
            "Error interno del servidor MCP. Reintenta más tarde.",
            correlation_id=correlation_id,
        )
    context.record(str(result.get("status", ToolStatus.INTERNAL_ERROR.value)))
    return result
