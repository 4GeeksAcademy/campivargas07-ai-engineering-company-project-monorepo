"""OAuth 2.1 resource-server wiring via MCP Auth (`mcpauth`).

The MCP server is a pure resource server:
- It publishes RFC 9728 Protected Resource Metadata (public) so any MCP
  client can discover the external authorization server.
- It verifies bearer JWTs against that provider (signature via JWKS, issuer,
  audience == resource id, expiry, and per-tool scopes).
- It NEVER uses FastMCP's built-in auth layer and never issues tokens itself.

The auth server config is normally discovered from the issuer
(`fetch_server_config`); tests inject a pre-built `AuthServerConfig`.
"""

from __future__ import annotations

from mcpauth import MCPAuth
from mcpauth.config import AuthServerConfig, AuthServerType
from mcpauth.types import ResourceServerConfig, ResourceServerMetadata
from mcpauth.utils import fetch_server_config

from .config import Settings
from .scopes import ALL_SCOPES


def create_mcp_auth(
    settings: Settings,
    auth_server_config: AuthServerConfig | None = None,
) -> MCPAuth:
    """Build the MCPAuth resource server for the configured protected resource."""
    if auth_server_config is None:
        # Real provider discovery (RFC 8414 / OIDC): network call at startup.
        auth_server_config = fetch_server_config(
            settings.auth_issuer, AuthServerType(settings.auth_server_type)
        )
    return MCPAuth(
        protected_resources=[
            ResourceServerConfig(
                metadata=ResourceServerMetadata(
                    resource=settings.resource_id,
                    authorization_servers=[auth_server_config],
                    scopes_supported=list(ALL_SCOPES),
                    resource_name="Brasaland MCP",
                    bearer_methods_supported=["header"],
                )
            )
        ]
    )
