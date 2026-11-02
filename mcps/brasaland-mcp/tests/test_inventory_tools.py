"""Inventory tools: real reads with mandatory local_id, writes impossible.

The write-rejection evidence required by the ticket:
1. No write tool exists: calling an invented write tool name is rejected by
   the MCP server itself.
2. Read tools reject extra/write-like arguments via their typed schemas.
3. Even if a call somehow reached the client layer, the backend policy
   rejects non-GET /inventory/* before any network I/O (unit-tested in
   test_backend_client.py).
In every case the mock backend records ZERO write requests.
"""

from __future__ import annotations

import uuid
import logging

import pytest

from .conftest import SAMPLE_PRODUCT, call_tool

PRODUCT_UUID = "2b6d7f9a-1c2e-4a3b-9d8f-0a1b2c3d4e5f"
LOCAL_ID = "MED-001"


def _payload(outcome) -> dict:
    assert outcome.payload is not None, f"expected envelope, got error: {outcome.error}"
    return outcome.payload


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def test_list_products_requires_local_id_semantics(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response("GET", "/inventory/products", 200, [SAMPLE_PRODUCT])
    outcome = call_tool(mcp_server, token_readonly, "list_inventory_products", {"local_id": LOCAL_ID})
    payload = _payload(outcome)
    assert payload["status"] == "success"
    assert payload["data"]["count"] == 1
    assert payload["data"]["products"][0]["sku"] == "ING-001"
    assert payload["data"]["products"][0]["current_stock"] == "25.0"
    req = mock_brasaland.requests[-1]
    assert (req.method, req.path, req.params) == ("GET", "/inventory/products", {"local_id": LOCAL_ID})


def test_list_products_empty_local_id_validation_error(mcp_server, token_readonly, mock_brasaland):
    outcome = call_tool(mcp_server, token_readonly, "list_inventory_products", {"local_id": "  "})
    payload = _payload(outcome)
    assert payload["status"] == "validation_error"
    assert payload["field"] == "local_id"
    assert mock_brasaland.requests == []


def test_get_product_success(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response("GET", f"/inventory/products/{PRODUCT_UUID}", 200, SAMPLE_PRODUCT)
    outcome = call_tool(
        mcp_server,
        token_readonly,
        "get_inventory_product",
        {"product_id": PRODUCT_UUID, "local_id": LOCAL_ID},
    )
    payload = _payload(outcome)
    assert payload["status"] == "success"
    assert payload["data"]["id"] == PRODUCT_UUID
    req = mock_brasaland.requests[-1]
    assert (req.method, req.path, req.params) == (
        "GET",
        f"/inventory/products/{PRODUCT_UUID}",
        {"local_id": LOCAL_ID},
    )


def test_get_product_rejects_sku_as_id(mcp_server, token_readonly, mock_brasaland):
    outcome = call_tool(
        mcp_server, token_readonly, "get_inventory_product", {"product_id": "ING-001", "local_id": LOCAL_ID}
    )
    payload = _payload(outcome)
    assert payload["status"] == "validation_error"
    assert payload["field"] == "product_id"
    assert mock_brasaland.requests == []


def test_get_product_not_found(mcp_server, token_readonly, mock_brasaland):
    mock_brasaland.set_response(
        "GET", f"/inventory/products/{PRODUCT_UUID}", 404, {"detail": "Product not found"}
    )
    outcome = call_tool(
        mcp_server,
        token_readonly,
        "get_inventory_product",
        {"product_id": PRODUCT_UUID, "local_id": LOCAL_ID},
    )
    assert _payload(outcome)["status"] == "not_found"


def test_inventory_requires_inventory_scope(mcp_server, mock_brasaland, oidc_provider):
    # Token with only incidents scopes: inventory must be refused.
    token = oidc_provider.mint(["incidents:read", "incidents:write"], aud=mcp_server.resource_id)
    outcome = call_tool(mcp_server, token, "list_inventory_products", {"local_id": LOCAL_ID})
    assert _payload(outcome)["status"] == "insufficient_scope"
    assert mock_brasaland.requests == []


# ---------------------------------------------------------------------------
# Write rejection (the core read-only guarantee)
# ---------------------------------------------------------------------------

INVENTED_WRITE_TOOLS = [
    ("update_inventory_product", {"product_id": PRODUCT_UUID, "local_id": LOCAL_ID, "minimum_stock": 999}),
    ("create_inventory_product", {"sku": "ING-999", "name": "x", "category": "carne"}),
    ("create_inbound_order", {"ingredient_id": PRODUCT_UUID, "local_id": LOCAL_ID, "quantity": 10}),
    ("create_outbound_order", {"ingredient_id": PRODUCT_UUID, "local_id": LOCAL_ID, "quantity": 10}),
    ("delete_inventory_product", {"product_id": PRODUCT_UUID}),
]


@pytest.mark.parametrize("tool_name,arguments", INVENTED_WRITE_TOOLS)
def test_invented_write_tools_are_rejected_and_never_reach_backend(
    mcp_server, token_full, mock_brasaland, tool_name, arguments, caplog
):
    with caplog.at_level(logging.INFO, logger="brasaland_mcp.audit"):
        outcome = call_tool(mcp_server, token_full, tool_name, arguments)
    # The MCP server itself rejects the unknown tool (protocol/tool error).
    assert outcome.payload is None or outcome.payload.get("status") != "success"
    assert outcome.is_error or (outcome.payload and outcome.payload["status"] != "success") or outcome.error
    assert mock_brasaland.write_requests() == []
    assert mock_brasaland.requests == []
    records = [r.msg for r in caplog.records if r.name == "brasaland_mcp.audit"]
    assert len(records) == 1
    assert records[0]["tool"] == tool_name
    assert records[0]["status"] == "tool_error"
    assert records[0]["client_id"] == "test-client"
    assert token_full not in str(records)


def test_read_tool_rejects_write_arguments(mcp_server, token_full, mock_brasaland, caplog):
    """Extra write-like arguments do not match the typed input schema."""
    mock_brasaland.set_response("GET", "/inventory/products", 200, [])
    with caplog.at_level(logging.INFO, logger="brasaland_mcp.audit"):
        outcome = call_tool(
            mcp_server,
            token_full,
            "list_inventory_products",
            {"local_id": LOCAL_ID, "current_stock": 0, "minimum_stock": 999},
        )
    assert mock_brasaland.requests == []
    assert outcome.is_error or outcome.error or (outcome.payload and outcome.payload["status"] != "success")
    assert mock_brasaland.write_requests() == []
    records = [r.msg for r in caplog.records if r.name == "brasaland_mcp.audit"]
    assert len(records) == 1
    assert records[0]["tool"] == "list_inventory_products"
    assert records[0]["status"] == "validation_error"
    assert records[0]["client_id"] == "test-client"
    assert records[0]["correlation_id"]
    assert token_full not in str(records)
    assert "current_stock" not in str(records)
    assert "minimum_stock" not in str(records)


def test_no_inventory_write_tool_in_discovery(mcp_server, token_full):
    from .conftest import list_tools

    tools = list_tools(mcp_server, token_full)
    names = {tool.name for tool in tools}
    inventory_tools = {name for name in names if "inventory" in name}
    assert inventory_tools == {"list_inventory_products", "get_inventory_product"}
    # discovery documents read-only intent
    for tool in tools:
        if tool.name in inventory_tools:
            assert tool.annotations is not None
            assert tool.annotations.readOnlyHint is True


def test_discovery_describes_local_id_vs_branch(mcp_server, token_full):
    from .conftest import list_tools

    tools = list_tools(mcp_server, token_full)
    by_name = {tool.name: tool for tool in tools}
    description = by_name["list_inventory_products"].description
    assert "local_id" in description
    assert "MED-001" in description
    # explicitly distinguishes inventory local_id from incident branch
    assert "branch" in description.lower()
    schema = by_name["list_inventory_products"].inputSchema
    assert "local_id" in schema.get("required", [])
