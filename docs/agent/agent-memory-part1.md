# MEM-092 — Memoria y Auto-mejora de Agentes (Parte 1/2)

## Base Git
- Rama: `feature/agent-memory`
- Base: `77a9379` (merge de PR #32, incluye MCP y herramienta externa de incidencias)
- `main` (`a1fe693`) no contiene MCP; la PR de memoria debe integrar ese trabajo.

## Almacenamiento elegido
TinyDB dedicado (`services/api/data/agent_memory.json`), tablas `memories`, `proposals`, `audits`, `conversations`. Separado del corpus RAG (Qdrant) y de incidentes. Lock de proceso + idempotencia por `proposal_id` y hash de contenido.

## Flujo implementado
`consulta → lectura de recuerdos permitidos → respuesta + propuesta opcional → decisión explícita → auditoría → consolidación solo si aprobada`

## Extensión HTTP
`POST /agent/query` acepta `conversation_id` y `client_request_id` opcionales. Si no llega `conversation_id`, el servidor genera `conv-<uuid>`. La respuesta incluye `conversation_id`, `run_id`, `route` y `memory_proposal` (cuando existe), con `exclude_none=True`.

## Archivos principales
- `services/api/app/domains/agent/memory.py`
- `services/api/app/domains/agent/state.py`
- `services/api/app/domains/agent/graph.py`
- `services/api/app/domains/agent/router.py`
- `services/api/tests/test_agent_memory.py`
- `services/api/tests/conftest.py` (aislamiento)
- `data/pipelines/rag.py` (`generate_answer_with_memory`)

## Política
La allowlist de categorías memorables está vacía por defecto (`AGENT_MEMORY_ALLOWED_CATEGORIES`); la política oficial del BRIEFING sigue pendiente. Las pruebas inyectan una política explícita.

## Evidencia simulada (almacenamiento temporal, proveedor simulado)

### Ciclo 1 — propuesta aprobada
- Turno 1: propuesta creada (`prop-62d6231b3da2`, estado `pending`).
- Resolución: `approve` → memoria consolidada (`mem-cf3d7bfe5d8e`).
- Turno 2: la memoria se recuperó y se incluyó en la respuesta (`Memoria recibida: [{'memory_id': 'mem-cf3d7bfe5d8e', ...}]`).

### Ciclo 2 — propuesta rechazada
- Turno 1: propuesta creada (`prop-88d1db759a42`, estado `pending`).
- Resolución: `reject` → estado `rejected`.
- Turno 2: no se recuperó memoria (`Memoria recibida: []`); `read_relevant_memories` vacío.

## Verificación
- `uv run python -m pytest` (services/api): `170 passed, 5 skipped`
- `tests/test_agent_memory.py`: `11 passed`
- `python -m compileall app/domains/agent`: OK

## Pendientes reales
- BRIEFING oficial de memoria (hechos permitidos/prohibidos, audiencia/alcance) para desbloquear reglas de contenido.
- Integración real con proveedor RAG (las pruebas usan proveedor simulado).
- Evaluación de clasificación de confirmación con LLM real (actualmente heurística explícita).
- Migración a PostgreSQL si se requiere concurrencia multi-proceso.
