# Inventario de componentes de IA — Brasaland

**Base auditada:** `feature/nist-security-practices` desde `origin/feature/owasp-top10-audit @ f377183` (PR #40 abierta/draft, dependiente de PR #39).  
**Fecha:** 2026-11-02.  
**Alcance:** componentes presentes en esta base. No se inventan sistemas no implementados.

## Leyenda de estado
- **Presente:** implementado y verificable en esta base.
- **Pendiente en otra PR:** existe en una rama/PR abierta pero no en esta base.
- **No implementado:** no existe en el repositorio; se documenta como brecha, no se crea.

## Componentes

### 1. Agente de soporte a gerentes (Manager support agent)
- **Propósito:** responder consultas operativas de gerentes de local (incidencias, inventario, manuales).
- **Ubicación:** `services/api/app/domains/agent/` (`router.py`, `graph.py`, `streaming.py`, `guardrails.py`, `memory.py`, `mcp_client.py`, `traces.py`, `state.py`).
- **Entradas externas:** `POST /agent/query` (question 1–2000 chars, conversation_id opcional); WebSocket `user_message`.
- **Salidas:** answer, route, run_id, conversation_id, memory_proposal.
- **Datos tratados/persistencia:** preguntas (no persistidas completas en traces, solo longitud), contexto RAG, incidentes, memorias TinyDB (`services/api/data/agent_memory.json`), traces JSON (`services/api/data/agent_traces/`).
- **Proveedor/modelo:** Google Gemini (`gemini-embedding-001`, `gemini-3.5-flash-lite`) vía RAG; sin herramientas de escritura.
- **Herramientas/permisos:** `retrieve_knowledge`, `query_incidents_mcp` (solo lectura, scope `incidents:read`), `read_memory`.
- **Responsable negocio:** Felipe Guerrero (Operaciones). **Técnico:** Nicolás Park (CTO).
- **Controles existentes:** guardrails (clasificación de intención, sanitización RAG/memoria, validación de salida, scope de herramientas), memoria con términos prohibidos, traces sanitizados, rate limiting HTTP/WS (nuevo).
- **Brechas:** rate limiting compartido entre procesos no existe (in-memory); bypass exhaustivo de prompt injection pendiente; traces no incluyen razonamiento privado (correcto) pero falta correlación con SSE/chat en algunos flujos.
- **Evidencia:** `services/api/tests/test_security_prompt_injection.py`, `test_agent_api.py`, `test_agent_evals.py`.

### 2. RAG y base de conocimiento
- **Propósito:** responder sobre recetas, alérgenos, desperdicio, proveedores y lealtad.
- **Ubicación:** `data/pipelines/rag.py`, `services/api/app/domains/knowledge/router.py`, Qdrant (`brasaland_knowledge`).
- **Entradas:** `POST /knowledge/query` (autenticado), texto de consulta.
- **Salidas:** respuesta generada + fragmentos recuperados.
- **Datos:** documentos oficiales (4 manuales), chunks con payload; Qdrant persistente.
- **Proveedor/modelo:** Gemini embeddings + generación; Qdrant 1.16.3.
- **Controles:** umbral `RAG_MIN_SCORE=0.60`, abstención sin evidencia, sanitización de chunks, rate limiting (nuevo).
- **Brechas:** depende de configuración externa; si no configurado responde 503.
- **Evidencia:** `docs/rag/rag-evaluation-report.md`, `data/eval/rag-evaluation-01.json`.

### 3. Memoria y propuestas de auto-mejora
- **Propósito:** recordar correcciones operativas por location, contexto de escalación, preferencias de comunicación.
- **Ubicación:** `services/api/app/domains/agent/memory.py`, TinyDB `agent_memory.json`.
- **Entradas:** propuestas generadas por el agente; decisiones explícitas del usuario.
- **Salidas:** memoria activa, propuestas pendientes.
- **Datos:** hechos memorables por `user_uuid` + `conversation_id`; auditoría.
- **Controles:** categorías permitidas, términos prohibidos (Brasa Points, PII, nómina), validación de candidato, deduplicación, expiración, límites.
- **Brechas:** concurrencia multi-proceso no garantizada; clasificación con LLM real pendiente.
- **Evidencia:** `services/api/tests/test_agent_memory.py`.

### 4. Servidor MCP y herramientas
- **Propósito:** exponer herramientas tipadas al agente sobre incidentes e inventario.
- **Ubicación:** `mcps/brasaland-mcp/` (zona protegida), 6 herramientas.
- **Entradas:** llamadas MCP autenticadas por OAuth.
- **Salidas:** resultados de incidentes/inventario.
- **Datos:** incidentes, productos de inventario (solo lectura).
- **Proveedor:** Auth0 (OAuth resource server); backend Brasaland.
- **Herramientas/permisos:** `get_incident`, `list_incidents`, `create_incident`, `update_incident_status`, `list_inventory_products`, `get_inventory_product`. Inventario solo lectura por diseño.
- **Controles:** OAuth, scopes, validación de argumentos, auditoría de invocación.
- **Brechas:** el JWT real de prueba contiene 3 scopes (`incidents:read`, `incidents:write`, `inventory:read`); minimo privilegio del cliente del agente pendiente de verificación. Zona protegida: cambios requieren confirmación explícita.
- **Evidencia:** `mcps/brasaland-mcp/tests/`, PR #32.

### 5. Chat WebSocket en tiempo real
- **Propósito:** chat de soporte con streaming del agente.
- **Ubicación:** `services/api/app/domains/chat/router.py`, `service.py`, `pubsub.py`, `repository.py`.
- **Entradas:** WebSocket `/chat/ws`, eventos `user_message`, `interrupt_requested`.
- **Salidas:** `token_chunk`, `generation_completed`, `session_snapshot`, errores.
- **Datos:** mensajes de chat (TinyDB), sesiones, generaciones.
- **Controles:** validación de Origin, límite 8 KB por frame, autenticación por primer frame, aislamiento por usuario/sesión, rate limiting por usuario (nuevo).
- **Brechas:** rate limiting por proceso (in-memory); checkpoint durable opcional no configurado por defecto.
- **Evidencia:** `services/api/tests/test_chat_*` (si existen), OWASP F-04/F-08.

### 6. Dashboard SSE de tickets RFP
- **Propósito:** push de eventos de nuevos tickets RFP al dashboard operativo.
- **Ubicación:** `services/api/app/domains/rfp/events.py`, `services/api/app/domains/rfp/router.py` (`GET /rfp-requests/events`).
- **Entradas:** conexión SSE autenticada, `Last-Event-ID`.
- **Salidas:** eventos `rfp_ticket_created`, keep-alive.
- **Datos:** tickets RFP (PostgreSQL), payload sanitizado.
- **Controles:** `can_view_rfp_event` (ownership/admin), expiración de token en conexión larga.
- **Brechas:** sin rate limiting específico para SSE (no invoca modelo directamente).
- **Evidencia:** `services/api/tests/test_rfp_*`.

### 7. Workflows RFP e aprobaciones
- **Propósito:** intake, clasificación, generación y evaluación de respuestas RFP por departamento, con aprobación humana.
- **Ubicación:** `services/api/app/domains/rfp/`, `data/pipelines/rfp_response_generation.py`, `data/pipelines/rfp_approval.py`.
- **Entradas:** upload PDF (límite 10 MB), generación, decisiones por departamento/CEO.
- **Salidas:** borradores, evaluaciones, documento final.
- **Datos:** RFP en PostgreSQL, archivos en `data/raw`.
- **Proveedor:** Gemini (RFP_GENERATION_*), con fallback RAG opcional.
- **Controles:** ownership de tickets, límite de tamaño, aprobación humana por departamento/CEO (Parte 3).
- **Brechas:** no hay aprobación humana para pedidos a proveedor automatizados (no existe tal automatización).
- **Evidencia:** `services/api/tests/test_rfp_part1/2/3.py`.

### 8. Telemetría
- **Propósito:** recepción de eventos de producto (sin persistencia).
- **Ubicación:** `services/api/app/domains/telemetry/`.
- **Entradas:** `POST /telemetry/events` (público, sin auth, hasta 20 eventos).
- **Salidas:** `{"received": N}`.
- **Controles:** validación Pydantic `extra="forbid"`, Zero-PII, rate limiting.
- **Brechas:** endpoint público por decisión (no persiste datos); pendiente de decisión de producto.
- **Evidencia:** OWASP R-03.

### 9. Integraciones de terceros
- **Google Gemini:** embeddings y generación (RAG, RFP). Credenciales vía env, nunca en repo.
- **Auth0:** OAuth para MCP y auth de API. Minimo privilegio pendiente de verificación.
- **Resend:** envío de correo de recuperación de contraseña.
- **Qdrant:** almacenamiento vectorial local (`127.0.0.1:6333`).
- **PostgreSQL/Mongo/TinyDB:** datos operativos.
- **Responsabilidad compartida:** el proveedor gestiona infraestructura/modelo; Brasaland gestiona configuración, scopes, datos enviados y manejo de credenciales.

## Componentes pendientes en otras PRs
- `feature/websocket-chat` (PR #39): chat en tiempo real (ya integrado en base OWASP).
- `feature/sse-notifications`: notificaciones SSE (integrado).
- `feature/rfp-*`: RFP (integrado).

## Componentes no implementados (no creados)
- Campañas/notificaciones masivas a clientes: no existe backend.
- Ajuste/anulación de puntos Brasa Points: no existe backend.
- Pedido automatizado a proveedor por encima de umbral: no existe (solo RFP).
- Ejecutor de SQL/código generado por modelo: no existe (y no se crea).

## Secretos y credenciales
- Configuración vía `.env` / `.env.example` (raíz y `services/api`).
- No se imprimen valores en este inventario ni en logs/traces.
- Secretos históricos detectados por gitleaks (8 hallazgos en commits antiguos de `services/api/.env` y falsos positivos en tests). Rotación no realizada; requiere autorización específica con acción, objetivo y rollback.