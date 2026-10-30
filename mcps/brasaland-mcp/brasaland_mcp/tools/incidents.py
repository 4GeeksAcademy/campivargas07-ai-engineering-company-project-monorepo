"""Incident tools backed exclusively by the real Brasaland Incidents Manager.

Routes used (no others exist for this domain):
- GET   /api/incidents            list with the backend's own filters
- GET   /api/incidents/{id}       single incident by internal 12-hex id
- POST  /api/incidents            create (validation owned by the backend)
- PATCH /api/incidents/{id}/status lifecycle transition (state machine owned
                                  by the backend; there is no generic PATCH)

All business validation (field rules, enum values, allowed transitions,
terminal states) stays in the backend; this module only shapes calls, maps
errors and documents the real domain vocabulary for MCP discovery.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..errors import ToolStatus, classify_backend_error, fail, ok
from ..scopes import INCIDENTS_READ, INCIDENTS_WRITE
from . import ToolDeps, execute_tool

INCIDENT_ID_PATTERN = re.compile(r"^[0-9a-fA-F]{12}$")

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
CREATES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
TRANSITIONS = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)


def _invalid_id(correlation_id: str) -> dict[str, Any]:
    return fail(
        ToolStatus.VALIDATION_ERROR,
        "incident_id debe ser el ID interno de la incidencia: 12 caracteres "
        "hexadecimales (por ejemplo 3f2a9c1b4d5e). Las referencias cortas o "
        "externas no son IDs internos.",
        correlation_id=correlation_id,
        field="incident_id",
    )


def register_incident_tools(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register the four incident tools on the given FastMCP server."""

    @mcp.tool(
        name="get_incident",
        description=(
            "Consulta una incidencia individual del Incidents Manager de Brasaland "
            "por su ID interno. Requiere el scope 'incidents:read'. Devuelve los "
            "campos reales de la API: id, title, description, category, status, "
            "branch, reported_at, updated_at, origin y external_ref. Estados "
            "posibles: open, in_progress, resolved, discarded. "
            "Error not_found si el ID no existe."
        ),
        annotations=READ_ONLY,
    )
    def get_incident(incident_id: str) -> dict[str, Any]:
        """Get a single Brasaland incident by its internal 12-hex-character id.

        Args:
            incident_id: internal incident id (exactly 12 hexadecimal characters).
        """

        def handler(correlation_id: str) -> dict[str, Any]:
            if not INCIDENT_ID_PATTERN.fullmatch(incident_id or ""):
                return _invalid_id(correlation_id)
            response = deps.backend.request("GET", f"/api/incidents/{incident_id.lower()}")
            if response.ok:
                return ok(response.body, "Incidencia encontrada.", correlation_id=correlation_id)
            status, message, field = classify_backend_error(
                response.status_code, response.body, endpoint="read"
            )
            return fail(status, message, correlation_id=correlation_id, field=field)

        return execute_tool(deps, "get_incident", (INCIDENTS_READ,), handler)

    @mcp.tool(
        name="list_incidents",
        description=(
            "Lista incidencias del Incidents Manager de Brasaland con los filtros "
            "reales de su API (todos opcionales; sin filtros devuelve todas). "
            "Requiere el scope 'incidents:read'. Filtros: status (open, "
            "in_progress, resolved, discarded), category (CUSTOMER_COMPLAINT, "
            "EQUIPMENT, SUPPLY, FOOD_QUALITY, STAFF), branch (COL-01..COL-10, "
            "FLA-01..FLA-04, HQ-MDE). Los valores inválidos los rechaza el "
            "backend con validation_error."
        ),
        annotations=READ_ONLY,
    )
    def list_incidents(
        status: Optional[str] = None,
        category: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> dict[str, Any]:
        """List Brasaland incidents using the backend's real list filters.

        Args:
            status: filter by lifecycle status (open|in_progress|resolved|discarded).
            category: filter by category (CUSTOMER_COMPLAINT|EQUIPMENT|SUPPLY|FOOD_QUALITY|STAFF).
            branch: filter by branch code (COL-01..COL-10|FLA-01..FLA-04|HQ-MDE).
        """

        def handler(correlation_id: str) -> dict[str, Any]:
            params = {
                key: value
                for key, value in (
                    ("status", status),
                    ("category", category),
                    ("branch", branch),
                )
                if value is not None
            }
            response = deps.backend.request("GET", "/api/incidents", params=params or None)
            if response.ok:
                incidents = response.body if isinstance(response.body, list) else []
                return ok(
                    {"incidents": incidents, "count": len(incidents)},
                    "Listado de incidencias completado.",
                    correlation_id=correlation_id,
                )
            error_status, message, field = classify_backend_error(
                response.status_code, response.body, endpoint="list"
            )
            return fail(error_status, message, correlation_id=correlation_id, field=field)

        return execute_tool(deps, "list_incidents", (INCIDENTS_READ,), handler)

    @mcp.tool(
        name="create_incident",
        description=(
            "Crea una incidencia en el Incidents Manager de Brasaland mediante "
            "POST /api/incidents. Requiere el scope 'incidents:write'. La "
            "validación de campos y los valores de dominio los aplica el "
            "backend: title (3-200 caracteres), description (mínimo 5), "
            "category (CUSTOMER_COMPLAINT, EQUIPMENT, SUPPLY, FOOD_QUALITY, "
            "STAFF), branch (COL-01..COL-10, FLA-01..FLA-04, HQ-MDE). La "
            "incidencia nace en status 'open' con origin 'api'. Devuelve la "
            "incidencia creada con su ID interno de 12 hexadecimales."
        ),
        annotations=CREATES,
    )
    def create_incident(
        title: str,
        description: str,
        category: str,
        branch: str,
    ) -> dict[str, Any]:
        """Create a Brasaland incident through the backend's real POST endpoint.

        Args:
            title: short summary (3-200 characters, validated by the backend).
            description: detailed report (minimum 5 characters, backend-validated).
            category: one of CUSTOMER_COMPLAINT|EQUIPMENT|SUPPLY|FOOD_QUALITY|STAFF.
            branch: one of COL-01..COL-10|FLA-01..FLA-04|HQ-MDE.
        """

        def handler(correlation_id: str) -> dict[str, Any]:
            response = deps.backend.request(
                "POST",
                "/api/incidents",
                json_body={
                    "title": title,
                    "description": description,
                    "category": category,
                    "branch": branch,
                },
            )
            if response.ok:
                return ok(response.body, "Incidencia creada.", correlation_id=correlation_id)
            status, message, field = classify_backend_error(
                response.status_code, response.body, endpoint="create"
            )
            return fail(status, message, correlation_id=correlation_id, field=field)

        return execute_tool(deps, "create_incident", (INCIDENTS_WRITE,), handler)

    @mcp.tool(
        name="update_incident_status",
        description=(
            "Cambia el estado de una incidencia EXCLUSIVAMENTE mediante el "
            "endpoint de ciclo de vida PATCH /api/incidents/{id}/status. "
            "Requiere el scope 'incidents:write'. La máquina de estados la "
            "aplica el backend: open -> in_progress|discarded; in_progress -> "
            "resolved|discarded; resolved y discarded son terminales. Devuelve "
            "invalid_transition si el backend rechaza el cambio, not_found si "
            "el ID no existe y validation_error si el estado destino no es "
            "open|in_progress|resolved|discarded."
        ),
        annotations=TRANSITIONS,
    )
    def update_incident_status(incident_id: str, status: str) -> dict[str, Any]:
        """Transition an incident's status via the backend lifecycle endpoint.

        Args:
            incident_id: internal incident id (exactly 12 hexadecimal characters).
            status: target status (in_progress|resolved|discarded; backend-enforced).
        """

        def handler(correlation_id: str) -> dict[str, Any]:
            if not INCIDENT_ID_PATTERN.fullmatch(incident_id or ""):
                return _invalid_id(correlation_id)
            response = deps.backend.request(
                "PATCH",
                f"/api/incidents/{incident_id.lower()}/status",
                json_body={"status": status},
            )
            if response.ok:
                return ok(
                    response.body,
                    f"Estado de la incidencia actualizado a {status!r}.",
                    correlation_id=correlation_id,
                )
            error_status, message, field = classify_backend_error(
                response.status_code, response.body, endpoint="status"
            )
            return fail(error_status, message, correlation_id=correlation_id, field=field)

        return execute_tool(deps, "update_incident_status", (INCIDENTS_WRITE,), handler)
