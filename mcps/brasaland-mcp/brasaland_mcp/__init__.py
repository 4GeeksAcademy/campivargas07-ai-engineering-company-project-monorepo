"""Brasaland MCP server package.

An OAuth 2.1-protected MCP resource server that exposes the *real* Brasaland
incidents and inventory capabilities to any authorized MCP client, and is
consumed by the LangGraph support agent through `langchain-mcp-adapters`.

Two trust boundaries are kept strictly separate:

1. client -> MCP: OAuth 2.1 / OIDC access tokens verified with `mcpauth`
   (resource-server mode). No valid token => no tool discovery, no tool call.
2. MCP -> Brasaland API: a dedicated MCP service account logs in through the
   real `POST /auth/login` and the resulting backend JWT is cached in memory.
   The user's authorization is enforced at boundary 1 (per-operation scopes);
   the backend sees a stable, auditable service identity.

Credentials never enter prompts, agent state, checkpoints, traces, logs or Git.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
