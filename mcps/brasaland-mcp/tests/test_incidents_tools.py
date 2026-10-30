"""Incident tools over the real MCP protocol against the mock backend.

Asserts exact backend routes (POST /api/incidents, PATCH /{id}/status),
scope enforcement per tool, the error taxonomy and audit logging.
"""

from __future__ import annotations

import logging

import pytest

from .conftest import SAMPLE_INCIDENT, call_tool

INCIDENT_ID = "3f2a9c1b4d5e"


def _payload(outcome) -> dict:
    assert outcome.payload is not None, f"expected envelope, got error: {outcome.error}"
    return outcome.payload


# ---------------------------------------------------------------------------
# get_incident
# ---------------------------------------------------------------------------


def test_get_incident_success(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response("GET", f"/api/incidents/{INCIDENT_ID}", 200, SAMPLE_INCIDENT)
    outcome = call_tool(mcp_server, token_readonly, "get_incident", {"incident_id": INCIDENT_ID})
    payload = _payload(outcome)
    assert payload["status"] == "success"
    assert payload["data"]["id"] == INCIDENT_ID
    assert payload["data"]["category"] == "EQUIPMENT"
    req = mock_brasaland.requests[-1]
    assert (req.method, req.path) == ("GET", f"/api/incidents/{INCIDENT_ID}")
    assert req.has_auth  # service JWT present towards the backend


def test_get_incident_invalid_id_format_never_hits_backend(mcp_server, token_readonly, mock_brasaland):
    outcome = call_tool(mcp_server, token_readonly, "get_incident", {"incident_id": "482"})
    payload = _payload(outcome)
    assert payload["status"] == "validation_error"
    assert payload["field"] == "incident_id"
    assert mock_brasaland.requests == []


def test_get_incident_not_found(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response(
        "GET",
        f"/api/incidents/{INCIDENT_ID}",
        404,
        {"code": 404, "message": "Incident not found", "field": None, "request_id": "r1"},
    )
    outcome = call_tool(mcp_server, token_readonly, "get_incident", {"incident_id": INCIDENT_ID})
    assert _payload(outcome)["status"] == "not_found"


# ---------------------------------------------------------------------------
# list_incidents
# ---------------------------------------------------------------------------


def test_list_incidents_passes_real_filters(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response("GET", "/api/incidents", 200, [SAMPLE_INCIDENT])
    outcome = call_tool(
        mcp_server,
        token_readonly,
        "list_incidents",
        {"status": "open", "category": "EQUIPMENT", "branch": "MED-01"},
    )
    payload = _payload(outcome)
    assert payload["status"] == "success"
    assert payload["data"]["count"] == 1
    req = mock_brasaland.requests[-1]
    assert (req.method, req.path) == ("GET", "/api/incidents")
    assert req.params == {"status": "open", "category": "EQUIPMENT", "branch": "MED-01"}


def test_list_incidents_invalid_filter_is_backend_validation(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response(
        "GET",
        "/api/incidents",
        400,
        {"code": 400, "message": "Invalid status: 'banana'", "field": "status", "request_id": "r2"},
    )
    outcome = call_tool(mcp_server, token_readonly, "list_incidents", {"status": "banana"})
    payload = _payload(outcome)
    assert payload["status"] == "validation_error"
    assert payload["field"] == "status"


# ---------------------------------------------------------------------------
# create_incident — exclusively via POST /api/incidents
# ---------------------------------------------------------------------------


def test_create_incident_uses_real_post_route(mcp_server, token_full, mock_brasaland):
    created = dict(SAMPLE_INCIDENT, status="open", origin="api")
    mock_brasaland.set_response("POST", "/api/incidents", 201, created)
    outcome = call_tool(
        mcp_server,
        token_full,
        "create_incident",
        {
            "title": "Parrilla con temperatura irregular",
            "description": "La parrilla principal no alcanza la temperatura objetivo.",
            "category": "EQUIPMENT",
            "branch": "MED-01",
        },
    )
    payload = _payload(outcome)
    assert payload["status"] == "success"
    req = mock_brasaland.requests[-1]
    assert (req.method, req.path) == ("POST", "/api/incidents")
    assert req.body["category"] == "EQUIPMENT"
    assert req.body["branch"] == "MED-01"


def test_create_incident_backend_validation_error(mcp_server, token_full, mock_brasaland):
    mock_brasaland.set_response(
        "POST",
        "/api/incidents",
        400,
        {"code": 400, "message": "[category] Unknown category", "field": "category", "request_id": "r3"},
    )
    outcome = call_tool(
        mcp_server,
        token_full,
        "create_incident",
        {"title": "Prueba", "description": "Descripción mínima", "category": "OTRA", "branch": "MED-01"},
    )
    payload = _payload(outcome)
    assert payload["status"] == "validation_error"
    assert payload["field"] == "category"


def test_create_incident_requires_write_scope(mcp_server, token_readonly, mock_brasaland):
    outcome = call_tool(
        mcp_server,
        token_readonly,
        "create_incident",
        {"title": "Prueba", "description": "Descripción mínima", "category": "EQUIPMENT", "branch": "MED-01"},
    )
    payload = _payload(outcome)
    assert payload["status"] == "insufficient_scope"
    assert "incidents:write" in payload["message"]
    assert mock_brasaland.requests == []  # never reaches the backend


# ---------------------------------------------------------------------------
# update_incident_status — exclusively via PATCH /{id}/status
# ---------------------------------------------------------------------------


def test_update_status_uses_lifecycle_route(mcp_server, token_full, mock_brasaland):
    mock_brasaland.set_response(
        "PATCH", f"/api/incidents/{INCIDENT_ID}/status", 200, dict(SAMPLE_INCIDENT, status="in_progress")
    )
    outcome = call_tool(
        mcp_server, token_full, "update_incident_status", {"incident_id": INCIDENT_ID, "status": "in_progress"}
    )
    payload = _payload(outcome)
    assert payload["status"] == "success"
    assert payload["data"]["status"] == "in_progress"
    req = mock_brasaland.requests[-1]
    assert (req.method, req.path) == ("PATCH", f"/api/incidents/{INCIDENT_ID}/status")
    assert req.body == {"status": "in_progress"}


def test_update_status_invalid_transition(mcp_server, token_full, mock_brasaland):
    mock_brasaland.set_response(
        "PATCH",
        f"/api/incidents/{INCIDENT_ID}/status",
        400,
        {
            "code": 400,
            "message": "Cannot transition from 'open' to 'resolved'. Allowed transitions from 'open': in_progress, discarded",
            "field": "status",
            "request_id": "r4",
        },
    )
    outcome = call_tool(
        mcp_server, token_full, "update_incident_status", {"incident_id": INCIDENT_ID, "status": "resolved"}
    )
    assert _payload(outcome)["status"] == "invalid_transition"


def test_update_status_terminal_state(mcp_server, token_full, mock_brasaland):
    mock_brasaland.set_response(
        "PATCH",
        f"/api/incidents/{INCIDENT_ID}/status",
        400,
        {
            "code": 400,
            "message": "Incident is in terminal state 'resolved' and cannot be updated.",
            "field": None,
            "request_id": "r5",
        },
    )
    outcome = call_tool(
        mcp_server, token_full, "update_incident_status", {"incident_id": INCIDENT_ID, "status": "open"}
    )
    assert _payload(outcome)["status"] == "invalid_transition"


def test_update_status_requires_write_scope(mcp_server, token_readonly, mock_brasaland):
    outcome = call_tool(
        mcp_server, token_readonly, "update_incident_status", {"incident_id": INCIDENT_ID, "status": "in_progress"}
    )
    assert _payload(outcome)["status"] == "insufficient_scope"
    assert mock_brasaland.requests == []


# ---------------------------------------------------------------------------
# Availability and audit
# ---------------------------------------------------------------------------


def test_backend_timeout_maps_to_envelope(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.raise_timeout = True
    mock_brasaland.set_response("GET", f"/api/incidents/{INCIDENT_ID}", 200, SAMPLE_INCIDENT)
    outcome = call_tool(mcp_server, token_readonly, "get_incident", {"incident_id": INCIDENT_ID})
    assert _payload(outcome)["status"] == "backend_timeout"


def test_backend_unreachable_maps_to_envelope(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.raise_connect_error = True
    outcome = call_tool(mcp_server, token_readonly, "list_incidents", {})
    assert _payload(outcome)["status"] == "backend_unavailable"


def test_backend_5xx_maps_to_unavailable(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response("GET", "/api/incidents", 503, {"detail": "down"})
    outcome = call_tool(mcp_server, token_readonly, "list_incidents", {})
    assert _payload(outcome)["status"] == "backend_unavailable"


def test_audit_log_records_invocation_without_secrets(mcp_server, token_full, mock_brasaland, caplog):
    mock_brasaland.set_response("GET", f"/api/incidents/{INCIDENT_ID}", 200, SAMPLE_INCIDENT)
    with caplog.at_level(logging.INFO, logger="brasaland_mcp.audit"):
        call_tool(mcp_server, token_full, "get_incident", {"incident_id": INCIDENT_ID})
    audit_lines = [r.getMessage() for r in caplog.records if r.name == "brasaland_mcp.audit"]
    assert len(audit_lines) == 1, "expected exactly one audit line per invocation"
    line = audit_lines[-1]
    assert "get_incident" in line
    assert "success" in line
    assert "test-client" in line  # OAuth client_id recorded
    assert "test-user-1" in line  # OAuth subject recorded
    assert "service-jwt-token" not in line  # backend token never logged
    assert token_full not in line  # OAuth token never logged
    assert "Parrilla" not in line  # incident content never logged
