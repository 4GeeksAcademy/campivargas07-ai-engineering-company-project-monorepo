# Brasaland MCP — Servidor MCP de incidencias e inventario

Servidor **Model Context Protocol (MCP)** independiente que expone las
capacidades reales del **Incidents Manager** y del **inventario** de Brasaland
a cualquier cliente MCP autorizado, protegido con **OAuth 2.1 vía
[MCP Auth](https://mcp-auth.dev)** (paquete `mcpauth`, modo *resource
server*). No usa la capa de auth integrada de FastMCP.

## Transporte: Streamable HTTP (y por qué)

- **Múltiples clientes remotos**: el agente LangGraph, MCP Playground y
  futuros clientes se conectan por HTTP(S); `stdio` sólo serviría a un
  proceso local.
- **OAuth**: la especificación de autorización MCP (RFC 9728 Protected
  Resource Metadata + challenge `401 WWW-Authenticate`) aplica al transporte
  HTTP; es lo que `mcpauth` monta sobre Starlette.
- **Un solo puerto** (por defecto `9100`), sin infraestructura adicional.
- Compatible con MCP Playground y con `langchain-mcp-adapters`
  (`transport="streamable_http"`).

## Arquitectura y dos fronteras de confianza

```
cliente MCP ──(1) OAuth 2.1: JWT verificado con mcpauth──▶ Brasaland MCP ──(2) JWT de cuenta de servicio──▶ API Brasaland
```

1. **cliente → MCP**: access token OAuth emitido por un proveedor externo
   (OIDC/OAuth 2.1). El MCP valida firma (JWKS), `iss`, `aud` (= resource
   id), expiración y scopes. Sin token válido no hay `initialize`, ni
   `tools/list`, ni `tools/call` (401 en transporte). La metadata OAuth es
   pública; el discovery de herramientas no.
2. **MCP → API Brasaland**: el MCP usa una **cuenta de servicio dedicada**
   (`MCP_BACKEND_SERVICE_EMAIL/PASSWORD`) que inicia sesión por el
   `POST /auth/login` real; el JWT del backend se cachea en memoria y se
   refresca antes de expirar. **No** hay passthrough del token del cliente
   (emisor/audiencia distintos), **no** se copia `SECRET_KEY` y no hay tokens
   hardcodeados. La autorización del usuario se ejerce en la frontera 1
   (scopes por operación) y su identidad OAuth (`client_id`, `sub`) queda en
   el log de auditoría.

## Herramientas y scopes (mínimo privilegio)

| Tool | Ruta real del backend | Scope |
|---|---|---|
| `get_incident(incident_id)` | `GET /api/incidents/{id}` | `incidents:read` |
| `list_incidents(status?, category?, branch?)` | `GET /api/incidents` | `incidents:read` |
| `create_incident(title, description, category, branch)` | `POST /api/incidents` | `incidents:write` |
| `update_incident_status(incident_id, status)` | `PATCH /api/incidents/{id}/status` (única vía; sin PATCH genérico) | `incidents:write` |
| `list_inventory_products(local_id)` | `GET /inventory/products?local_id=` | `inventory:read` |
| `get_inventory_product(product_id, local_id)` | `GET /inventory/products/{id}?local_id=` | `inventory:read` |

Vocabulario real de Brasaland (validado **por el backend**, no duplicado
aquí): estados `open|in_progress|resolved|discarded` con transiciones
`open→{in_progress,discarded}`, `in_progress→{resolved,discarded}` y estados
terminales; categorías `CUSTOMER_COMPLAINT|EQUIPMENT|SUPPLY|FOOD_QUALITY|STAFF`;
branches `COL-01..COL-10|FLA-01..FLA-04|HQ-MDE`; IDs internos de incidencia
de 12 caracteres hexadecimales.

**Inventario es sólo lectura por diseño, en tres capas:**

1. No existe ninguna tool de escritura; discovery lo documenta
   (`readOnlyHint` es señal, no autorización).
2. Las entradas están estrictamente tipadas; no hay argumentos de escritura.
3. `backend._check_policy` **rechaza localmente** cualquier método no-GET
   hacia `/inventory/*` antes de tocar la red
   (`write_not_supported`): un intento de modificación nunca alcanza una
   operación de escritura del backend (demostrado en tests).

⚠️ `local_id` (inventario, p. ej. `MED-001`, `MIA-001`) es **obligatorio** y
**no** es el `branch` de incidencias (`COL-xx/FLA-xx/HQ-MDE`).

## Taxonomía de errores

Nivel transporte (middleware `mcpauth`, antes de existir sesión MCP):

| Situación | Respuesta HTTP |
|---|---|
| Sin header `Authorization` / token inválido / expirado / firma, `iss` o `aud` incorrectos | `401` + `WWW-Authenticate` con `resource_metadata` (códigos `missing_auth_header`, `invalid_token`, `invalid_issuer`, `invalid_audience`, …) |
| Error del proveedor OAuth al verificar | `500` genérico (sin detalles internos) |

Nivel tool (envelope estructurado `{status, message, correlation_id, field?}`):

| `status` | Significado |
|---|---|
| `success` | operación completada (`data`) |
| `validation_error` | entrada rechazada por el backend (400/422, con `field` cuando aplica) |
| `not_found` | incidencia/producto inexistente (404) |
| `invalid_transition` | la máquina de estados del backend rechazó el cambio (400 en `/status`) |
| `duplicate` | incidencia duplicada (409) |
| `insufficient_scope` | token válido sin el scope requerido por la tool |
| `write_not_supported` | escritura intentada sobre superficie de sólo lectura |
| `backend_timeout` | la API excedió `MCP_BACKEND_TIMEOUT_SECONDS` |
| `backend_unavailable` | API inalcanzable, 5xx o credencial de servicio rechazada |
| `internal_error` | fallo inesperado (detalles nunca expuestos) |

## Auditoría

Cada invocación registra una línea JSON en el logger `brasaland_mcp.audit`:
`correlation_id`, `client_id` y `subject` OAuth, `tool`, `status` y
`duration_ms`. **Nunca** tokens, bodies, preguntas ni contenido de
incidencias.

Los rechazos de esquema anteriores a la tool se auditan como
`validation_error`; otros errores MCP de invocacion, como una tool inexistente,
como `tool_error`. Se conserva el error MCP original sin registrar su texto
ni los argumentos. Las llamadas que llegan al ejecutor mantienen su unico
registro habitual; los rechazos OAuth de transporte no son invocaciones de tool.

## Configuración (sólo entorno; nada de secretos en Git)

| Variable | Obligatoria | Descripción |
|---|---|---|
| `MCP_RESOURCE_ID` | sí | Identificador público del recurso (RFC 8707) y `aud` esperado. En Codespaces: la **URL HTTPS pública reenviada** del puerto MCP, p. ej. `https://<codespace>-9100.app.github.dev/mcp` |
| `MCP_AUTH_ISSUER` | sí | Issuer OIDC/OAuth 2.1 del proveedor (discovery + JWKS) |
| `MCP_AUTH_SERVER_TYPE` | no (`oidc`) | `oidc` o `oauth` (RFC 8414) |
| `BRASALAND_API_URL` | sí | URL interna del backend FastAPI (p. ej. `http://127.0.0.1:8000`); no se expone públicamente |
| `MCP_BACKEND_SERVICE_EMAIL` | sí | Email de la cuenta de servicio MCP en Brasaland |
| `MCP_BACKEND_SERVICE_PASSWORD` | sí | Password de la cuenta de servicio |
| `MCP_BACKEND_TIMEOUT_SECONDS` | no (`5.0`) | Timeout HTTP hacia el backend |
| `MCP_HOST` / `MCP_PORT` | no (`127.0.0.1`/`9100`) | Bind del servidor; en Codespaces usar `0.0.0.0` |
| `MCP_LOG_LEVEL` | no (`INFO`) | Nivel de log |

Ver `.env.example`. El proveedor OAuth debe poder emitir JWTs con
`aud = MCP_RESOURCE_ID` y los scopes `incidents:read`, `incidents:write`,
`inventory:read`.

## Ejecución

```bash
cd mcps/brasaland-mcp
uv sync --all-groups
cp .env.example .env  # completar con valores reales (fuera de Git)
set -a; source .env; set +a
uv run brasaland-mcp
```

Discovery rápido (requiere token OAuth válido):

```bash
curl -s "$MCP_RESOURCE_ID" -H "Authorization: Bearer $ACCESS_TOKEN"   # 401 sin token
curl -s "${MCP_RESOURCE_ID%/*}/.well-known/oauth-protected-resource/mcp"  # metadata pública
```

## Pruebas

```bash
cd mcps/brasaland-mcp
uv run pytest            # unitarias (transporte mock, proveedor OIDC mock local)
uv run pytest -m integration   # requieren backend real (TEST_DATABASE_URL etc.)
```

Las pruebas unitarias usan un **proveedor OIDC mock local** (JWKS real, tokens
RS256 reales) y un transporte httpx mock del backend: verifican firma,
issuer, audiencia, expiración y scopes de verdad, sin proveedor externo. Las
pruebas de integración contra backend real están marcadas `integration` y
usan recursos aislados, nunca datos de producción.

## Validación en MCP Playground

Con el servidor corriendo en Codespaces y el puerto 9100 reenviado con
visibilidad pública: pegar en <https://www.mcpplayground.tech/playground> la
**URL HTTPS pública reenviada** (no localhost), autenticarse con el
proveedor OAuth y ejecutar un flujo completo por tool (incluido el intento
de escritura sobre inventario, que debe fallar de forma controlada con
`write_not_supported`). Sólo se publica el puerto del MCP; el backend no se
expone.

## Cliente del agente LangGraph

El agente (`services/api/app/domains/agent/mcp_client.py`) consume este
servidor con `langchain-mcp-adapters` usando client-credentials OAuth con
**sólo `incidents:read`**. No existe fallback HTTP directo al Incidents
Manager: si el MCP falla, el agente responde `unavailable`/`timeout` de forma
explícita.


## Inspector: diagnostico de conexion con Bearer

En Inspector 2.13.0: agregar el servidor con Streamable HTTP y su URL /mcp.
En Settings > Custom Headers, usar una sola fila Authorization con valor
`Bearer TOKEN`: un espacio y el access_token completo, sin repetir Bearer,
sin comillas y sin pegar el JSON de Auth0. El valor debe tener dos palabras.
El SDK ya envia `Accept: application/json, text/event-stream`; no duplicarlo.
Cerrar Settings y reconectar para aplicar los cambios.

Si aparece `Incompatible auth server: does not support dynamic client registration`,
revisar primero Network y el 401 anterior. En la validacion del 29-oct-2026,
el error era secundario a un Bearer mal formado/invalido o al tunel privado:
con un access_token valido el Inspector conecto sin registrar otro cliente OAuth.
Un cliente que necesite login OAuth interactivo requiere su registro/configuracion
propios; las credenciales M2M no sustituyen ese flujo.

En Codespaces comprobar que 9100 sigue publico tras reiniciar el proceso.
El backend 8000 y PostgreSQL deben seguir privados. Un initialize correcto no
prueba la autenticacion del backend: ejecutar una herramienta y revisar su status.
`backend_unavailable` en inventario puede provenir de DATABASE_URL ausente;
la base debe estar disponible y las tablas inicializadas segun el proyecto.

Para el agente, usar una M2M con grant exclusivo `incidents:read` y comprobar
los scopes del JWT emitido. No asumir que pedir ese scope en el request reduce
los permisos de un cliente Auth0 autorizado para los tres scopes. Mantener
otro cliente para las pruebas que necesitan crear/actualizar incidencias.
