# Carpeta `mcps`

Esta carpeta contiene los **Servidores Model Context Protocol (MCP)** que exponen herramientas, recursos y contexto a los modelos y agentes de IA.

Cada subcarpeta dentro de `mcps/` debe corresponder a **un servidor MCP concreto** (por ejemplo `database-mcp`, `github-mcp`) e incluir su propia documentación.

- **Propósito principal**: centralizar los servidores que actúan como puente entre los modelos de IA y los sistemas internos o fuentes de datos de la compañía.
- **Recomendación**: documenta las herramientas y recursos que expone cada servidor MCP.

## Servidores disponibles

- [`mcps/brasaland-mcp/`](brasaland-mcp/): servidor MCP de Brasaland, protegido con OAuth 2.1
  (`mcpauth`, modo resource server). Expone las capacidades reales de incidencias
  (`get_incident`, `list_incidents`, `create_incident`,
  `update_incident_status`) e inventario (`list_inventory_products`,
  `get_inventory_product`, sólo lectura) mediante Streamable HTTP. Transporte,
  scopes, discovery, códigos de error y validación en su propio README.
