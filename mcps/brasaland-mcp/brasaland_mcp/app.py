"""Starlette assembly: public metadata + healthz, OAuth-gated MCP endpoint.

Route order matters: the public routes (healthz, RFC 9728 metadata) are
registered before the catch-all Mount, so they are reachable without a token.
Everything under the Mount (the MCP streamable-http endpoint at /mcp) passes
through the mcpauth bearer middleware: without a valid access token there is
no initialize, no tools/list and no tools/call.
"""

from __future__ import annotations

import contextlib

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcpauth import MCPAuth
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .auth import create_mcp_auth
from .backend import BrasalandBackend
from .config import Settings
from .tools import ToolDeps
from .tools.incidents import register_incident_tools
from .tools.inventory import register_inventory_tools

SERVER_NAME = "Brasaland MCP"

SERVER_INSTRUCTIONS = (
    "Servidor MCP de Brasaland (cadena de restaurantes, Colombia y Florida). "
    "Expone las capacidades reales del Incidents Manager y del inventario. "
    "Scopes: incidents:read (get_incident, list_incidents), incidents:write "
    "(create_incident, update_incident_status — transiciones validadas por el "
    "backend vía PATCH /api/incidents/{id}/status), inventory:read "
    "(list_inventory_products, get_inventory_product — sólo lectura; cualquier "
    "escritura sobre inventario se rechaza explícitamente). Los IDs internos "
    "de incidencia son 12 caracteres hexadecimales; local_id de inventario "
    "(MED-001, MIA-001) es distinto del branch de incidencias (COL-xx, "
    "FLA-xx, HQ-MDE)."
)


async def healthz(request: Request) -> JSONResponse:
    """Public liveness probe; exposes nothing about the tools."""
    return JSONResponse({"status": "ok"})


def build_app(
    settings: Settings,
    *,
    mcp_auth: MCPAuth | None = None,
    backend: BrasalandBackend | None = None,
) -> Starlette:
    """Build the full ASGI app. Dependencies are injectable for tests."""
    if mcp_auth is None:
        mcp_auth = create_mcp_auth(settings)
    if backend is None:
        backend = BrasalandBackend(
            settings.backend_url,
            email=settings.backend_email,
            password=settings.backend_password,
            timeout_seconds=settings.backend_timeout_seconds,
        )

    mcp = FastMCP(name=SERVER_NAME, stateless_http=True, instructions=SERVER_INSTRUCTIONS)
    deps = ToolDeps(mcp_auth=mcp_auth, backend=backend)
    register_incident_tools(mcp, deps)
    register_inventory_tools(mcp, deps)

    # FastMCP otherwise discards extra arguments before calling a tool.
    @mcp._mcp_server.list_tools()
    async def list_strict_tools():
        tools = await mcp.list_tools()
        for tool in tools:
            tool.inputSchema["additionalProperties"] = False
        return tools

    mcp._mcp_server.call_tool(validate_input=True)(mcp.call_tool)

    # streamable_http_app() must be called before accessing session_manager.
    mcp_http_app = mcp.streamable_http_app()

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with contextlib.AsyncExitStack() as stack:
            await stack.enter_async_context(mcp.session_manager.run())
            yield
            backend.close()

    bearer_auth = Middleware(
        mcp_auth.bearer_auth_middleware(
            "jwt",
            # audience enforces aud == resource id (RFC 8707); resource selects
            # the token verifier for this protected resource.
            audience=settings.resource_id,
            resource=settings.resource_id,
        )
    )

    return Starlette(
        routes=[
            Route("/healthz", healthz, methods=["GET"]),
            *mcp_auth.resource_metadata_router().routes,
            Mount("/", app=mcp_http_app, middleware=[bearer_auth]),
        ],
        lifespan=lifespan,
    )


def serve(settings: Settings) -> None:
    """Run the MCP server with uvicorn (single published port)."""
    app = build_app(settings)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
