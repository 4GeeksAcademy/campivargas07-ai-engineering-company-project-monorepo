# MEM-092 — Aseguramiento de Agentes: Harness y Guardrails (Parte 2/2)

## Base Git

- Rama: `feature/agent-guardrails`
- Base: `de615e8` (PR #33, Parte 1 de memoria)
- PR #33 no se modificó ni se fusionó.

## Defensas implementadas

1. Clasificación de intención antes de herramientas o memoria.
2. Respuestas seguras para conversación casual, tareas personales e intentos de override.
3. Saneamiento de contenido externo (RAG, MCP, memoria).
4. Guardia de herramientas con allowlist de solo lectura.
5. Validación de salida para formato, fuga de instrucciones y datos prohibidos.
6. Protección de memoria: solicitudes bloqueadas no generan ni consolidan recuerdos.
7. Registro y resumen simple de activaciones de guardrails.

## Archivos principales

- `services/api/app/domains/agent/guardrails.py`
- `services/api/app/domains/agent/state.py`
- `services/api/app/domains/agent/graph.py`
- `services/api/app/domains/agent/memory.py`
- `services/api/tests/test_agent_guardrails.py`

## Verificación

- `PYTHONPATH=services/api:repo uv run pytest tests/test_agent_guardrails.py` → 13 passed.
- `PYTHONPATH=services/api:repo uv run pytest tests/test_agent_memory.py tests/test_agent_api.py tests/test_agent_mcp_credentials.py` → 28 passed.
- `PYTHONPATH=services/api:repo uv run pytest` → 183 passed, 5 skipped.
- `uv run python -m compileall app/domains/agent data` → OK.

## Pendientes reales

- Validación E2E con LLM real y servicios externos (RAG/MCP) no disponible.
- Concurrencia multi-proceso y almacenamiento PostgreSQL siguen diferidos de Parte 1.
