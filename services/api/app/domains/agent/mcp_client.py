"""MCP client used by the LangGraph agent (boundary: agent -> MCP server).

Replaces the former direct HTTP client (`incident_tool.py`). The agent no
longer calls the Incidents Manager by itself: it discovers and invokes the
MCP server's tools through `langchain-mcp-adapters` over Streamable HTTP,
authenticating with its own OAuth client-credentials token (scope
`incidents:read` only — no mutations by natural language).

No fallback to a direct HTTP call exists: if the MCP server is unavailable
or unauthorized, the agent reports it explicitly (`unavailable`/`timeout`).
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Any, Callable, Optional
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from data.process.config import ConfigurationError

INCIDENT_MCP_TIMEOUT_SECONDS = 5.0


class IncidentToolStatus(StrEnum):
    SUCCESS = "success"
    NOT_FOUND = "not_found"
    PERMISSION_DENIED = "permission_denied"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


class IncidentToolInput(BaseModel):
    """Only accepts the actual incident API ID or its supported list filters."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    incident_id: Annotated[str, Field(min_length=1, max_length=128)] | None = None
    status: str | None = None
    category: str | None = None
    branch: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in {"open", "in_progress", "resolved", "discarded"}:
            raise ValueError("Unsupported incident status filter.")
        return value

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.upper()
            if not value.startswith(("COL-", "FLA-", "HQ-")):
                raise ValueError("Unsupported incident branch filter.")
        return value

    @model_validator(mode="after")
    def validate_query(self):
        if self.incident_id is not None and any(
            value is not None for value in (self.status, self.category, self.branch)
        ):
            raise ValueError("Use an incident ID or list filters, not both.")
        return self


class IncidentRecord(BaseModel):
    """Operational fields consumed by the agent; free-text fields are dropped
    here so untrusted content is never sent to the model as instructions."""

    model_config = ConfigDict(extra="ignore")

    id: str
    category: str
    status: str
    branch: str
    reported_at: str
    updated_at: str
    origin: str
    external_ref: str | None = None


class IncidentToolResult(BaseModel):
    status: IncidentToolStatus
    incidents: list[IncidentRecord] = Field(default_factory=list)
    message: str


# ---------------------------------------------------------------------------
# OAuth client-credentials token provider (agent -> MCP server)
# ---------------------------------------------------------------------------


class _TokenCache:
    def __init__(self) -> None:
        self.token: str | None = None
        self.expires_at: float = 0.0
        self.lock = threading.Lock()


@dataclass
class McpTokenProvider:
    """Obtains and caches an OAuth access token via client credentials."""

    token_url: str
    client_id: str
    client_secret: str
    scopes: str
    audience: str | None = None
    _cache: _TokenCache = field(default_factory=_TokenCache)

    def get(self) -> str:
        with self._cache.lock:
            if self._cache.token and time.monotonic() < self._cache.expires_at:
                return self._cache.token
            token, ttl = self._fetch()
            self._cache.token = token
            self._cache.expires_at = time.monotonic() + max(ttl - 30.0, 1.0)
            return token

    def _fetch(self) -> tuple[str, float]:
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scopes,
        }
        if self.audience:
            data["audience"] = self.audience
        try:
            response = httpx.post(
                self.token_url,
                data=data,
                headers={"Accept": "application/json"},
                timeout=INCIDENT_MCP_TIMEOUT_SECONDS,
                follow_redirects=False,
            )
        except httpx.HTTPError as exc:
            raise ConfigurationError("MCP OAuth token endpoint unavailable") from exc
        if response.status_code >= 400:
            raise ConfigurationError(
                f"MCP OAuth token request failed ({response.status_code})"
            )
        try:
            payload = response.json()
            token = payload["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ConfigurationError("MCP OAuth token response malformed") from exc
        expires_in = payload.get("expires_in", 300)
        try:
            ttl = float(expires_in)
        except (TypeError, ValueError):
            ttl = 300.0
        return token, ttl


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    return value.strip() if isinstance(value, str) else value


def _resolve_server_url() -> str:
    url = _env("AGENT_MCP_SERVER_URL") or _env("MCP_SERVER_URL")
    if not url:
        raise ConfigurationError("AGENT_MCP_SERVER_URL is not configured")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError(f"Invalid AGENT_MCP_SERVER_URL: {url!r}")
    return url.rstrip("/")


def _resolve_token_provider() -> McpTokenProvider:
    token_url = _env("AGENT_MCP_TOKEN_URL") or _env("MCP_TOKEN_URL")
    client_id = _env("AGENT_MCP_CLIENT_ID") or _env("MCP_CLIENT_ID")
    client_secret = _env("AGENT_MCP_CLIENT_SECRET") or _env("MCP_CLIENT_SECRET")
    if not token_url or not client_id or not client_secret:
        raise ConfigurationError(
            "MCP client credentials are not configured "
            "(AGENT_MCP_TOKEN_URL/CLIENT_ID/CLIENT_SECRET)"
        )
    scopes = _env("AGENT_MCP_SCOPES", "incidents:read") or "incidents:read"
    audience = _env("AGENT_MCP_AUDIENCE") or _env("MCP_AUDIENCE")
    return McpTokenProvider(
        token_url=token_url,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes,
        audience=audience,
    )


# ---------------------------------------------------------------------------
# MCP invocation
# ---------------------------------------------------------------------------


def _status_from_envelope(status: str | None) -> IncidentToolStatus:
    mapping = {
        "success": IncidentToolStatus.SUCCESS,
        "not_found": IncidentToolStatus.NOT_FOUND,
        "insufficient_scope": IncidentToolStatus.PERMISSION_DENIED,
        "validation_error": IncidentToolStatus.UNAVAILABLE,  # surfaced as message
        "invalid_transition": IncidentToolStatus.UNAVAILABLE,
        "backend_timeout": IncidentToolStatus.TIMEOUT,
        "backend_unavailable": IncidentToolStatus.UNAVAILABLE,
        "write_not_supported": IncidentToolStatus.PERMISSION_DENIED,
        "duplicate": IncidentToolStatus.UNAVAILABLE,
        "internal_error": IncidentToolStatus.UNAVAILABLE,
    }
    return mapping.get(status or "", IncidentToolStatus.UNAVAILABLE)


async def _invoke_mcp_async(
    query: IncidentToolInput,
    *,
    server_url: str,
    token: str,
) -> IncidentToolResult:
    from langchain_mcp_adapters.client import MultiServerMCPClient

    client = MultiServerMCPClient(
        {
            "brasaland": {
                "transport": "streamable_http",
                "url": f"{server_url}/mcp" if not server_url.endswith("/mcp") else server_url,
                "headers": {"Authorization": f"Bearer {token}"},
            }
        }
    )
    tools = await client.get_tools()
    by_name = {tool.name: tool for tool in tools}

    if query.incident_id is not None:
        tool = by_name.get("get_incident")
        if tool is None:
            return IncidentToolResult(
                status=IncidentToolStatus.UNAVAILABLE,
                message="El servidor MCP de Brasaland no expone get_incident.",
            )
        raw = await tool.ainvoke({"incident_id": query.incident_id})
    else:
        tool = by_name.get("list_incidents")
        if tool is None:
            return IncidentToolResult(
                status=IncidentToolStatus.UNAVAILABLE,
                message="El servidor MCP de Brasaland no expone list_incidents.",
            )
        args = {
            key: value
            for key, value in {
                "status": query.status,
                "category": query.category,
                "branch": query.branch,
            }.items()
            if value is not None
        }
        raw = await tool.ainvoke(args)

    # langchain-mcp-adapters returns either a dict (structured) or a list of
    # content blocks; normalize to a dict envelope.
    envelope: dict[str, Any] | None = None
    if isinstance(raw, dict):
        envelope = raw
    elif isinstance(raw, list):
        for block in raw:
            text = getattr(block, "text", None) or (block.get("text") if isinstance(block, dict) else None)
            if text:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        envelope = parsed
                        break
                except (ValueError, TypeError):
                    continue
    if envelope is None:
        return IncidentToolResult(
            status=IncidentToolStatus.UNAVAILABLE,
            message="El servidor MCP devolvió una respuesta no válida.",
        )

    status = envelope.get("status")
    message = envelope.get("message") or "Consulta de incidencias completada."
    if status == "success":
        data = envelope.get("data")
        incidents_raw: list[Any] = []
        if isinstance(data, list):
            incidents_raw = data
        elif isinstance(data, dict):
            if isinstance(data.get("incidents"), list):
                incidents_raw = data["incidents"]
            elif "id" in data:
                incidents_raw = [data]
        incidents: list[IncidentRecord] = []
        for item in incidents_raw:
            try:
                incidents.append(IncidentRecord.model_validate(item))
            except Exception:
                continue
        return IncidentToolResult(
            status=IncidentToolStatus.SUCCESS,
            incidents=incidents,
            message=message,
        )

    mapped = _status_from_envelope(status)
    if mapped == IncidentToolStatus.UNAVAILABLE and status in {"validation_error", "invalid_transition"}:
        # Keep the backend's precise message visible to the agent.
        message = envelope.get("message") or message
    return IncidentToolResult(status=mapped, incidents=[], message=message)


def query_incidents_via_mcp(
    query: IncidentToolInput,
    *,
    server_url: str | None = None,
    token_provider: McpTokenProvider | None = None,
    tool_invoker: Callable[[IncidentToolInput, str, str], IncidentToolResult] | None = None,
    timeout_seconds: float = INCIDENT_MCP_TIMEOUT_SECONDS,
) -> IncidentToolResult:
    """Synchronous entry point used by the graph node.

    `tool_invoker` is injectable for tests; production uses the real adapter.
    """
    resolved_url = (server_url or _resolve_server_url()).rstrip("/")
    if tool_invoker is not None:

        async def _invoke() -> IncidentToolResult:
            return await asyncio.to_thread(tool_invoker, query, resolved_url, "test-token")

        token = "test-token"
    else:
        provider = token_provider or _resolve_token_provider()
        try:
            token = provider.get()
        except ConfigurationError:
            raise
        except Exception:
            return IncidentToolResult(
                status=IncidentToolStatus.UNAVAILABLE,
                message="No tengo permisos para consultar el gestor de incidencias.",
            )

        async def _invoke() -> IncidentToolResult:
            return await _invoke_mcp_async(query, server_url=resolved_url, token=token)

    async def _run() -> IncidentToolResult:
        try:
            return await asyncio.wait_for(_invoke(), timeout=timeout_seconds)
        except asyncio.TimeoutError:
            return IncidentToolResult(
                status=IncidentToolStatus.TIMEOUT,
                message="La consulta de incidencias excedió el tiempo límite; no pude confirmar los datos.",
            )
        except Exception:
            return IncidentToolResult(
                status=IncidentToolStatus.UNAVAILABLE,
                message="El servidor MCP de Brasaland no está disponible en este momento.",
            )

    try:
        return asyncio.run(_run())
    except RuntimeError:
        result_box: dict[str, IncidentToolResult] = {}

        def _worker() -> None:
            result_box["value"] = asyncio.run(_run())

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=timeout_seconds + 2)
        return result_box.get(
            "value",
            IncidentToolResult(
                status=IncidentToolStatus.TIMEOUT,
                message="La consulta de incidencias excedió el tiempo límite; no pude confirmar los datos.",
            ),
        )
