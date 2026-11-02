"""Transport-level auth: nothing works without a valid OAuth access token.

Covers the evaluation criterion "Un cliente sin access token OAuth válido no
puede listar ni ejecutar ninguna tool" and the distinct 401 error classes.
"""

from __future__ import annotations

import json

import httpx
import pytest

from .conftest import ToolCallOutcome, list_tools, run_mcp_session

MCP_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "auth-test", "version": "0"},
    },
}


def _raw_post(url: str, token: str | None) -> httpx.Response:
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if token is not None:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.post(url, json=MCP_INIT, headers=headers, timeout=10)


def test_initialize_without_token_is_rejected(mcp_server):
    resp = _raw_post(mcp_server.mcp_url, None)
    assert resp.status_code == 401
    challenge = resp.headers.get("www-authenticate", "")
    assert "resource_metadata" in challenge


def test_initialize_with_garbage_token_is_rejected(mcp_server):
    resp = _raw_post(mcp_server.mcp_url, "not-a-jwt")
    assert resp.status_code == 401


def test_initialize_with_expired_token_is_rejected(mcp_server, oidc_provider):
    token = oidc_provider.mint(["incidents:read"], aud=mcp_server.resource_id, exp_offset=-120)
    resp = _raw_post(mcp_server.mcp_url, token)
    assert resp.status_code == 401


def test_initialize_with_wrong_audience_is_rejected(mcp_server, oidc_provider):
    token = oidc_provider.mint(["incidents:read"], aud="https://otro-recurso.example/mcp")
    resp = _raw_post(mcp_server.mcp_url, token)
    assert resp.status_code == 401
    assert "invalid_audience" in resp.headers.get("www-authenticate", "")


def test_initialize_with_wrong_issuer_is_rejected(mcp_server, oidc_provider):
    token = oidc_provider.mint(
        ["incidents:read"], aud=mcp_server.resource_id, iss="https://issuer-desconocido.example"
    )
    resp = _raw_post(mcp_server.mcp_url, token)
    assert resp.status_code == 401
    assert "invalid_issuer" in resp.headers.get("www-authenticate", "")


def test_tools_list_without_token_is_rejected(mcp_server):
    outcome = list_tools(mcp_server, None)
    # The MCP session cannot even initialize: a transport error, never tools.
    assert isinstance(outcome, ToolCallOutcome) and outcome.error
    assert not isinstance(outcome, list)


def test_tools_call_without_token_never_reaches_backend(mcp_server, mock_brasaland):
    outcome = run_mcp_session(mcp_server.mcp_url, None, "call_tool", "list_incidents", {})
    assert isinstance(outcome, ToolCallOutcome) and outcome.error
    assert mock_brasaland.requests == []


def test_protected_resource_metadata_is_public(mcp_server):
    resp = httpx.get(mcp_server.metadata_url, timeout=10)
    assert resp.status_code == 200
    body = resp.json()
    assert body["resource"] == mcp_server.resource_id
    assert set(body["scopes_supported"]) == {"incidents:read", "incidents:write", "inventory:read"}
    # Public OAuth metadata never leaks tool definitions.
    assert "tools" not in json.dumps(body)


def test_healthz_is_public_and_reveals_nothing(mcp_server):
    resp = httpx.get(f"{mcp_server.base_url}/healthz", timeout=10)
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_valid_token_can_initialize_and_list(mcp_server, token_full):
    tools = list_tools(mcp_server, token_full)
    assert isinstance(tools, list)
    names = {tool.name for tool in tools}
    assert names == {
        "get_incident",
        "list_incidents",
        "create_incident",
        "update_incident_status",
        "list_inventory_products",
        "get_inventory_product",
    }
