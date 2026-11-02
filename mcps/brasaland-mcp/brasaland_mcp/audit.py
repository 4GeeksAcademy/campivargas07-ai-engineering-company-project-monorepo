"""Audit logging for every tool invocation.

One structured log line per call with: correlation id, OAuth client id and
subject (pseudonymous, from the verified token), tool name, result status, and
timing. Never logs tokens, request/response bodies, incident content or
credentials — only categorical metadata for traceability.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Optional

AUDIT_LOGGER_NAME = "brasaland_mcp.audit"

_logger = logging.getLogger(AUDIT_LOGGER_NAME)


@dataclass
class InvocationContext:
    """Non-sensitive metadata about a single tool invocation."""

    correlation_id: str
    tool: str
    client_id: Optional[str] = None
    subject: Optional[str] = None
    scopes: tuple[str, ...] = field(default_factory=tuple)
    _started: float = field(default_factory=perf_counter, repr=False)

    def record(self, status: str, *, extra: Optional[dict] = None) -> None:
        """Emit the audit line for this invocation with its result status."""
        payload = {
            "event": "mcp_tool_invocation",
            "correlation_id": self.correlation_id,
            "tool": self.tool,
            "client_id": self.client_id,
            "subject": self.subject,
            "scopes": list(self.scopes),
            "status": status,
            "duration_ms": round((perf_counter() - self._started) * 1000, 2),
        }
        if extra:
            # extra must be non-sensitive categorical data only
            payload.update(extra)
        _logger.info(payload)


def get_audit_logger() -> logging.Logger:
    return _logger
