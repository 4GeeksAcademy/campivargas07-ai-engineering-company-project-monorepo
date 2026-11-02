"""Inventory tools: strictly read-only, backed by the real Brasaland API.

Routes used (the only ones this server may issue for /inventory/*):
- GET /inventory/products            list with mandatory local_id
- GET /inventory/products/{id}       single product with stock for local_id

Read-only by design, in three layers:
1. No write tool is registered; discovery advertises `readOnlyHint` and the
   descriptions state the restriction (hint is documentation, not enforcement).
2. Tool inputs are strictly typed; there are no write arguments to pass.
3. `backend._check_policy` rejects any non-GET call to /inventory/* BEFORE it
   reaches the network, so even a hypothetical future bug cannot write. Any
   such attempt returns the `write_not_supported` envelope.

`local_id` is the inventory restaurant-location id (seeded locations such as
MED-001 or MIA-001). It is mandatory and is NOT the incident `branch` code
(COL-xx/FLA-xx/HQ-MDE); both are documented separately to avoid confusion.
"""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from ..errors import ToolStatus, classify_backend_error, fail, ok
from ..scopes import INVENTORY_READ
from . import ToolDeps, execute_tool

PRODUCT_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)

_LOCAL_ID_DOC = (
    "local_id es OBLIGATORIO: identificador del local de inventario "
    "(por ejemplo MED-001 o MIA-001). No es el branch de incidencias "
    "(COL-xx/FLA-xx/HQ-MDE)."
)


def register_inventory_tools(mcp: FastMCP, deps: ToolDeps) -> None:
    """Register the read-only inventory tools on the given FastMCP server."""

    @mcp.tool(
        name="list_inventory_products",
        description=(
            "Lista los ingredientes del catálogo de inventario de Brasaland con "
            "su stock dinámico calculado (current_stock = entradas - salidas) "
            "para un local. Sólo lectura: este servidor rechaza explícitamente "
            "cualquier operación de escritura sobre inventario "
            "(write_not_supported). Requiere el scope 'inventory:read'. "
            f"{_LOCAL_ID_DOC} Devuelve por producto: id (UUID), sku, name, "
            "category (carne, verdura, salsa, bebida, empaque, limpieza), "
            "unit_of_measure, minimum_stock, perishable, local_id y "
            "current_stock."
        ),
        annotations=READ_ONLY,
    )
    def list_inventory_products(local_id: str) -> dict[str, Any]:
        """List inventory products with calculated stock for one restaurant location.

        Args:
            local_id: mandatory inventory location id (e.g. MED-001, MIA-001).
        """

        def handler(correlation_id: str) -> dict[str, Any]:
            if not (local_id or "").strip():
                return fail(
                    ToolStatus.VALIDATION_ERROR,
                    _LOCAL_ID_DOC,
                    correlation_id=correlation_id,
                    field="local_id",
                )
            response = deps.backend.request(
                "GET", "/inventory/products", params={"local_id": local_id.strip()}
            )
            if response.ok:
                products = response.body if isinstance(response.body, list) else []
                return ok(
                    {"products": products, "count": len(products)},
                    "Listado de productos de inventario completado.",
                    correlation_id=correlation_id,
                )
            status, message, field = classify_backend_error(
                response.status_code, response.body, endpoint="read"
            )
            return fail(status, message, correlation_id=correlation_id, field=field)

        return execute_tool(deps, "list_inventory_products", (INVENTORY_READ,), handler)

    @mcp.tool(
        name="get_inventory_product",
        description=(
            "Consulta UN ingrediente del inventario de Brasaland por su UUID de "
            "catálogo con el stock dinámico calculado para un local. Sólo "
            "lectura: cualquier intento de modificación es rechazado "
            "explícitamente (write_not_supported). Requiere el scope "
            f"'inventory:read'. product_id es el UUID del producto (no el SKU "
            f"ING-xxx). {_LOCAL_ID_DOC} Devuelve not_found si el producto no "
            "existe y validation_error si el UUID o el local_id son inválidos."
        ),
        annotations=READ_ONLY,
    )
    def get_inventory_product(product_id: str, local_id: str) -> dict[str, Any]:
        """Get one inventory product (UUID) with its stock for a location.

        Args:
            product_id: product catalog UUID (not the ING-xxx SKU).
            local_id: mandatory inventory location id (e.g. MED-001, MIA-001).
        """

        def handler(correlation_id: str) -> dict[str, Any]:
            if not PRODUCT_ID_PATTERN.fullmatch(product_id or ""):
                return fail(
                    ToolStatus.VALIDATION_ERROR,
                    "product_id debe ser un UUID de catálogo (8-4-4-4-12 "
                    "hexadecimal), no un SKU ING-xxx.",
                    correlation_id=correlation_id,
                    field="product_id",
                )
            if not (local_id or "").strip():
                return fail(
                    ToolStatus.VALIDATION_ERROR,
                    _LOCAL_ID_DOC,
                    correlation_id=correlation_id,
                    field="local_id",
                )
            response = deps.backend.request(
                "GET",
                f"/inventory/products/{product_id.lower()}",
                params={"local_id": local_id.strip()},
            )
            if response.ok:
                return ok(response.body, "Producto de inventario encontrado.", correlation_id=correlation_id)
            status, message, field = classify_backend_error(
                response.status_code, response.body, endpoint="read"
            )
            return fail(status, message, correlation_id=correlation_id, field=field)

        return execute_tool(deps, "get_inventory_product", (INVENTORY_READ,), handler)
