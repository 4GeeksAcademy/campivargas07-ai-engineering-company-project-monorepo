# Auditoría y corrección de vulnerabilidades web — OWASP Top 10

## 1. Alcance y base auditada

- **Repositorio:** `4GeeksAcademy/campivargas07-ai-engineering-company-project-monorepo`
- **Rama de trabajo:** `feature/owasp-top10-audit`
- **Base auditada:** `origin/feature/websocket-chat @ 7eff737582fbb9c952b3f985e640d5d66c885db5` (PR #39, abierta/draft, no modificada)
- **Fecha de auditoría:** 2026-11-02
- **Entorno:** macOS local, Python 3.13.18, Node 24.14.1, Docker Compose local. No se verificó servidor Linux/SSH/firewall gestionado; se documenta como pendiente.
- **Matriz principal:** OWASP Top 10:2021 (IDs del BRIEFING). Correspondencia con OWASP 2025 incluida en la sección 7.

## 2. Inventario real

### Presente en la base auditada

- Backend activo: `services/api` (FastAPI), dominios auth, users, profiles, suppliers, incidents, inventory, telemetry, knowledge, agent, chat, rfp.
- Frontends: `uis/website`, `uis/backoffice`, `uis/loyalty-app`, `uis/operations-ui`.
- Agente de soporte: LangGraph, guardrails, memoria, streaming.
- RAG: `data/pipelines/rag.py`, Qdrant, knowledge base.
- MCP: `mcps/brasaland-mcp` (zona protegida), 6 herramientas, OAuth resource server.
- SSE: eventos de tickets RFP (`services/api/app/domains/rfp/events.py`).
- WebSocket: chat en tiempo real (`services/api/app/domains/chat`).
- RFP: intake, clasificación, generación y evaluación.
- Datos: TinyDB (usuarios, perfiles, proveedores, memoria, chat), PostgreSQL (inventario/RFP), Qdrant (conocimiento).
- Contenedores: `docker-compose.yml`, `infra/docker-compose.yml`, Dockerfiles.

### Fuera de alcance o no existente

- `services/backend` (legacy, fuera de alcance primario).
- `uis/talent-pipeline-tracker` (hito anterior).
- Integración real POS/loyalty/Brasa Points: no existe backend propio; solo frontend/telemetría/documentación.
- Pipeline automático de compras a proveedor: solo flujo RFP, no automatización de compra.
- Redis, Celery, WAF, CDN, pasarela de pago, servidor gestionado: no evidenciados.

## 3. Baseline

### Pruebas automatizadas (antes de cambios)

- Backend: `204 passed, 5 skipped` (`services/api/tests`, PostgreSQL omitido sin `TEST_DATABASE_URL`).
- MCP: `54 passed` (`mcps/brasaland-mcp/tests`).
- Frontend backoffice: `107 passed` (`uis/backoffice`).
- Typecheck frontend: 3 errores preexistentes en auth/telemetría; build frontend no ejecutado en esta corrida.

### Dependencias

- Python (`pip-audit`): `No known vulnerabilities found` para dependencias auditables de `services/api` y `mcps/brasaland-mcp`.
- Node (`npm audit`): 28 vulnerabilidades (18 moderate, 9 high, 1 critical), principalmente en tooling/dependencias transitivas (`undici`, `vite`, `zod`). No se aplicó `npm audit fix` por conflicto de peer dependencies; queda como pendiente separado.

### Secretos

- Búsqueda redactada en archivos rastreados: sin patrones típicos de claves privadas/API keys.
- Escaneo de historial completo no ejecutado por falta de herramienta instalada (`gitleaks`/`trufflehog`); se recomienda en una fase posterior.

### Puertos

- Compose raíz publica API `8000`, interfaces `3000/3001`, Qdrant solo `127.0.0.1:6333`.
- `infra/docker-compose.yml` publicaba PostgreSQL `5432`, Mongo `27017` y pgAdmin `5050` en todas las interfaces; corregido a `127.0.0.1`.

## 4. Matriz OWASP 2021 × capas

| Categoría | Backend | Frontend | Agéntico (agent/RAG/MCP/SSE/WS) |
|---|---|---|---|
| A01 Acceso roto | Hallazgo (RFP listado/resultados sin ownership; chat location allowlist por defecto) | Verificado (rutas protegidas) | Hallazgo (chat location por defecto permisivo; MCP scopes separados) |
| A02 Criptografía | Hallazgo (secreto JWT con default inseguro) | Verificado (token en localStorage, sin secretos versionados) | Verificado (MCP no reenvía token de usuario; TLS depende de despliegue) |
| A03 Inyección | Verificado (Pydantic/SQLModel parametrizado; sin eval/exec) | Verificado (sin `dangerouslySetInnerHTML`) | Hallazgo potencial (prompt injection mitigado por guardrails; evaluar bypass) |
| A04 Diseño inseguro | Hallazgo (telemetría sin auth; RFP sin límite de tamaño) | Verificado | Hallazgo (confirmación humana solo parcial en RFP) |
| A05 Configuración | Hallazgo (CORS wildcard, headers ausentes, puertos expuestos) | Verificado | Hallazgo (WebSocket sin Origin validado originalmente) |
| A06 Componentes | Verificado (pip-audit sin hallazgos) | Hallazgo (npm audit con vulnerabilidades) | Verificado |
| A07 Autenticación | Hallazgo (sin rate limiting en login; JWT default) | Verificado | Verificado (MCP OAuth resource server) |
| A08 Integridad | Verificado (lockfiles presentes) | Verificado | Verificado |
| A09 Logging/monitoreo | Parcial (auditoría MCP; timing sin datos sensibles) | Verificado | Parcial (traces sanitizados; memoria auditada) |
| A10 SSRF / condiciones excepcionales | Verificado (URLs RAG validadas; sin fetch de URL arbitraria por usuario) | Verificado | Parcial (manejo de excepciones en SSE/chat) |

## 5. Hallazgos y correcciones

### Correcciones aplicadas

| ID | Severidad | Categoría | Descripción | Archivo | Estado |
|---|---|---|---|---|---|
| F-01 | Alto | A02/A07 | Secreto JWT con default inseguro. | `services/api/app/domains/auth/service.py` | Corregido: secreto obligatorio fuera de dev/test; default solo en modos dev/test. |
| F-02 | Medio | A05 | CORS con métodos/headers wildcard. | `services/api/app/main.py` | Corregido: orígenes configurables, métodos y headers explícitos. |
| F-03 | Medio | A05 | Ausencia de headers de seguridad HTTP. | `services/api/app/main.py` | Corregido: middleware con nosniff, frame options, referrer policy, permissions policy, HSTS opcional. |
| F-04 | Medio | A05 | WebSocket sin validación de `Origin`. | `services/api/app/domains/chat/router.py` | Corregido: lista de orígenes permitidos configurable. |
| F-05 | Medio | A05/A04 | RFP sin límite de tamaño de archivo. | `services/api/app/domains/rfp/router.py` | Corregido: límite configurable de 10 MB por defecto. |
| F-06 | Medio | A01 | RFP listado y lectura sin control de ownership. | `services/api/app/domains/rfp/router.py` | Corregido: 404 para tickets ajenos; listado filtrado para no admin. |
| F-07 | Medio | A05 | Infraestructura de BD expuesta en todas las interfaces. | `infra/docker-compose.yml` | Corregido: bind a `127.0.0.1`. |
| F-08 | Bajo | A04 | Frame WebSocket sin límite de tamaño. | `services/api/app/domains/chat/router.py` | Corregido: límite de 8 KB por frame. |
| F-09 | Medio | A07/A02 | Token de chat en query string (riesgo de logs). | `uis/backoffice/src/lib/chat-socket.ts` | Parcialmente corregido: frontend autentica con primer frame; backend mantiene compatibilidad. |

### Hallazgos no corregidos / residuales

| ID | Severidad | Categoría | Descripción | Estado |
|---|---|---|---|---|
| R-01 | Alto (diseño) | A01 | `user_can_access_location()` permite por defecto si no hay allowlist. | Pendiente de decisión de producto; no se desactivó la funcionalidad para no romper operación. |
| R-02 | Medio | A07 | Sin rate limiting en `/auth/login` y endpoints sensibles. | Pendiente. |
| R-03 | Medio | A04 | Telemetría pública (`POST /telemetry/events`) sin autenticación. | Pendiente de decisión; actualmente no persiste datos. |
| R-04 | Medio | A06 | `npm audit`: 28 vulnerabilidades en dependencias frontend/tooling. | Pendiente por conflicto de peer deps; requiere PR separado. |
| R-05 | Bajo | A02 | Token JWT en `localStorage` (impacto XSS si apareciera XSS). | Mitigado por ausencia de `dangerouslySetInnerHTML`; evaluar cookies HttpOnly en futuro. |
| R-06 | Bajo | A09 | `except Exception: pass` en varios flujos. | No crítico; mejorar logging estructurado en fase posterior. |
| R-07 | Bajo | A03 | Prompt injection: guardrails presentes, pero no se demostró bypass exhaustivo. | Requiere pruebas adicionales con casos del BRIEFING. |
| R-08 | Información | A01 | Listado de usuarios (`GET /users`) expone datos a cualquier usuario autenticado. | Pendiente de política de roles. |
| R-09 | Información | A05 | Endpoints de proveedores GET públicos por diseño. | Verificar intención de negocio. |

### Evidencia antes/después

- Antes: `SECRET_KEY` default `"brasa-land-dev-secret-key-change-in-production"` en `auth/service.py`.
- Después: `_required_secret()` exige variable de entorno fuera de dev/test; tests establecen secreto explícito en `conftest.py`.
- Antes: CORS `allow_methods=["*"]`, `allow_headers=["*"]`.
- Después: métodos y headers explícitos y orígenes configurables.
- Antes: `infra/docker-compose.yml` publicaba `5432`, `27017`, `5050` en `0.0.0.0`.
- Después: bind a `127.0.0.1`.
- Antes: WebSocket sin validación de `Origin`.
- Después: `_allowed_websocket_origins()` configurable; origen inválido rechazado.
- Antes: RFP sin límite de tamaño.
- Después: `RFP_MAX_UPLOAD_BYTES` (default 10 MiB).
- Antes: RFP status/result/generate accesibles por cualquier ticket UUID.
- Después: 404 para tickets no propios (excepto admin).

### Verificación posterior

- Backend: `204 passed, 5 skipped` (pytest).
- MCP: `54 passed`.
- Frontend backoffice: `107 passed`.
- Typecheck frontend: 3 errores preexistentes sin nuevos errores introducidos por este cambio.
- `pip-audit`: sin vulnerabilidades conocidas en dependencias Python auditables.

## 6. Limitaciones y riesgos residuales

- No se verificó servidor Linux, SSH, firewall ni despliegue gestionado; solo configuración versionada y entorno local.
- No se ejecutaron escaneos activos DAST (ZAP) por falta de herramienta instalada y tiempo; se recomienda en una fase posterior.
- No se escaneó historial completo de Git con `gitleaks`/`trufflehog`.
- No se corrigieron las vulnerabilidades de `npm audit` por conflicto de peer dependencies.
- R-01 (allowlist de locations) sigue abierto por decisión de producto.
- No se declaran controles externos como aplicados; solo los cambios de código/configuración versionados y verificados.

## 7. Comandos reproducibles

```bash
# Baseline / verificación backend
cd services/api && python -m pytest -q

# MCP
cd mcps/brasaland-mcp && python -m pytest -q

# Frontend
npm --prefix uis/backoffice run test
npm run typecheck:uis

# Auditoría Python
services/api/.venv/bin/bandit -r services/api/app mcps/brasaland-mcp/brasaland_mcp -q
services/api/.venv/bin/pip-audit --path services/api
services/api/.venv/bin/pip-audit --path mcps/brasaland-mcp

# Node
npm audit
```

## 8. Fuentes oficiales

- OWASP Top 10:2021: https://owasp.org/Top10/2021/
- OWASP Top 10:2025: https://owasp.org/Top10/2025/
- BRIEFING Brasaland: https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/main/content/contexts/cybersecurity-analysis/brasaland-BRIEFING.es.md
- FastAPI security docs: https://fastapi.tiangolo.com/tutorial/security/
- MCP specification: https://modelcontextprotocol.io/

## 9. Conclusión

No se confirmaron vulnerabilidades críticas explotables en la base auditada. Se corrigieron hallazgos altos/medios acotados y se dejaron riesgos residuales documentados. El proyecto no se declara cerrado para producción hasta verificar controles de infraestructura externos y dependencias frontend.