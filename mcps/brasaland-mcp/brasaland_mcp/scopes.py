"""OAuth scopes for the Brasaland MCP resource server (least privilege).

Each tool requires exactly the scope it needs; a read-only client never needs a
write scope. These are the scopes the MCP server *understands* and advertises in
its Protected Resource Metadata; the OAuth provider must be configured to issue
them (see README).
"""

INCIDENTS_READ = "incidents:read"
"""Consultar incidencias por ID y listarlas con los filtros reales del backend."""

INCIDENTS_WRITE = "incidents:write"
"""Crear incidencias y cambiar su estado por el ciclo de vida real del backend."""

INVENTORY_READ = "inventory:read"
"""Consultar (nunca modificar) productos e inventario por local."""

ALL_SCOPES: tuple[str, ...] = (
    INCIDENTS_READ,
    INCIDENTS_WRITE,
    INVENTORY_READ,
)

# Scopes the LangGraph support agent client is expected to hold: read-only.
# The MCP exposes write operations for *other* authorized clients, but the
# agent keeps its current read-only behaviour (no natural-language mutations).
AGENT_SCOPES: tuple[str, ...] = (INCIDENTS_READ,)
