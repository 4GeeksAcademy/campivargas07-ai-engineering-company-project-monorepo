# Prácticas Seguras en la Integración de IA — Informe NIST CSF 2.0 (Brasaland)

**Marco:** NIST Cybersecurity Framework 2.0 (Govern, Identify, Protect, Detect, Respond, Recover).  
**No es** NIST AI RMF ni una certificación NIST.  
**Base:** `feature/nist-security-practices` desde `origin/feature/owasp-top10-audit @ f377183` (PR #40 abierta/draft).  
**Fecha:** 2026-11-02.  
**Inventario asociado:** `docs/security/ai-component-inventory.md`.  
**Auditoría OWASP previa:** `docs/security/owasp-top10-audit.md` (no sobrescrita; se enlaza).

## Estado de controles
- **Implementado:** verificable en código/pruebas en esta base.
- **Parcial:** existe pero con brecha documentada.
- **Futuro:** no implementado; requiere autorización o decisión.

## Tabla de acciones por función NIST

| ID | Función | Acción concreta | Responsable propuesto | Prioridad | Estado | Evidencia | Criterio de cierre |
|---|---|---|---|---|---|---|---|
| G-1 | Govern | Asignar responsable de seguridad de IA (CTO) y responsables de negocio por componente (Operations, Procurement, Marketing). | Nicolás Park (CTO) / Mariana Restrepo (CEO) | Alta | Parcial | `docs/security/ai-component-inventory.md` | Inventario con responsables aprobado y versionado. |
| G-2 | Govern | Gestionar terceros (Gemini, Auth0, Resend, Qdrant): contrato, scopes, datos enviados, rotación de credenciales. | Nicolás Park (CTO) | Alta | Parcial | `.env.example`, `mcp_client.py` | Matriz de terceros con responsable y revisión periódica. |
| G-3 | Govern | Política de memoria del agente (hechos permitidos/prohibidos) basada en BRIEFING. | Felipe Guerrero (Operaciones) | Media | Implementado | `memory.py` (`ALLOWED_MEMORY_CATEGORIES`, `PROHIBITED_MEMORY_TERMS`) | Categorías y términos prohibidos validados por pruebas. |
| I-1 | Identify | Inventario de componentes de IA, entradas/salidas, datos y persistencia. | Nicolás Park (CTO) | Alta | Implementado | `docs/security/ai-component-inventory.md` | Inventario completo y actualizado por hito. |
| I-2 | Identify | Límites de confianza: separar instrucciones del sistema de contenido no confiable (RAG, MCP, memoria). | Nicolás Park (CTO) | Alta | Implementado | `guardrails.py` (`sanitize_rag_chunks`, `sanitize_memory_context`, `sanitize_external_text`) | Pruebas de sanitización en verde. |
| I-3 | Identify | Riesgos de excesiva autonomía: herramientas solo lectura en MCP; no hay ejecutor de SQL/código. | Nicolás Park (CTO) | Alta | Implementado | `mcp_client.py`, `guard_tool_call` | Verificación de que ninguna herramienta de escritura es invocable por lenguaje natural. |
| P-1 | Protect | Credenciales: secreto JWT obligatorio fuera de dev/test; `.env` no versionado. | Nicolás Park (CTO) | Alta | Implementado | `auth/service.py` (`_required_secret`), `.gitignore` | `pip-audit`/tests en verde; gitleaks sin fugas en archivos actuales. |
| P-2 | Protect | Autorización por usuario/sesión/ubicación en servidor. | Nicolás Park (CTO) / Felipe Guerrero | Alta | Parcial | `chat/service.py` (`user_can_access_location`) | Decisión de producto sobre allowlist por location (R-01) cerrada y probada. |
| P-3 | Protect | Validación de entrada antes de invocar modelos (tipo, longitud, tamaño, estructura). | Nicolás Park (CTO) | Alta | Implementado | `agent/router.py` (max 2000), `streaming.py`, chat frame 8 KB, RFP 10 MB | Pruebas de entrada inválida en verde. |
| P-4 | Protect | Rate limiting de modelos en HTTP y WebSocket. | Nicolás Park (CTO) | Alta | Implementado | `app/common/rate_limit.py`, `main.py`, `chat/router.py` | `tests/test_rate_limiting.py` en verde; 429 sin llamada al proveedor. |
| P-5 | Protect | Confirmación humana para acciones irreversibles existentes (cambio/baja de proveedor). | Lucía Fernández (Procurement) / Nicolás Park | Alta | Implementado | `suppliers/router.py` (`confirm`, status, delete), `suppliers/confirmation.py`, `tests/test_suppliers_api.py` | Confirmación de un solo uso, expiración, anti-reutilización, validación de parámetros/actor y auditoría. |
| D-1 | Detect | Eventos de seguridad: guardrails, rate limiting, intentos de inyección. | Nicolás Park (CTO) | Media | Parcial | `guardrails.py` (`record_guardrail_event`), logs estructurados | Eventos consultables y correlacionables por run_id/session. |
| D-2 | Detect | Trazabilidad de flujos agénticos: usuario (UUID), sesión, ejecución, ruta/herramienta y razón, controles, resultado/error, timestamp. | Nicolás Park (CTO) | Alta | Implementado | `agent/traces.py`, `graph.py` (trace payloads) | Trace JSON con campos requeridos; prueba de redacción. |
| D-3 | Detect | Redacción en logs/traces: sin razonamiento privado, secretos ni mensajes completos. | Nicolás Park (CTO) | Alta | Implementado | `traces.py`, chat router (error genérico) | Pruebas de ausencia de tokens/argumentos. |
| R-1 | Respond | Contención: bloquear entrada inválida, aislamiento de sesión, revocar acceso. | Nicolás Park (CTO) / Felipe Guerrero | Alta | Parcial | Guardrails, WS auth | Procedimiento documentado y ensayado. |
| R-2 | Respond | Preservación de evidencia: traces, logs estructurados, auditoría de proveedores. | Nicolás Park (CTO) | Media | Parcial | `agent_traces/`, logs | Retención y acceso documentados. |
| R-3 | Respond | Comunicaciones: notificación a stakeholders (CEO, CTO, Operations). | Mariana Restrepo (CEO) | Media | Futuro | — | Cadena de contacto y plantilla de comunicación. |
| RC-1 | Recover | Restauración: reinicio de servicios, validación de salud, re-ejecución de pruebas. | Nicolás Park (CTO) | Media | Parcial | `/health`, pruebas automatizadas | Checklist de recuperación verificado. |
| RC-2 | Recover | Verificación post-incidente: regresión de agente, memoria, MCP, chat y SSE. | Nicolás Park (CTO) | Media | Parcial | Suite de pruebas | Suite verde tras recuperación. |

## Procedimiento de incidente y recuperación (aplicable al entorno real)

1. **Detección:** alerta por logs estructurados, guardrail events, errores 429/401/403 o reporte de usuario.
2. **Contención:** deshabilitar el componente afectado (feature flag o detener servicio), revocar tokens/credenciales comprometidas si aplica (requiere autorización específica), bloquear origen ofensivo.
3. **Preservación de evidencia:** conservar traces en `services/api/data/agent_traces/`, logs de guardrails y auditoría de proveedores; no modificar historial Git automáticamente.
4. **Erradicación:** corregir configuración/código, rotar credenciales solo con autorización explícita (acción, objetivo, rollback).
5. **Recuperación:** reiniciar servicios, verificar `/health`, ejecutar suite de pruebas, validar flujos afectados (agente, memoria, MCP, chat, SSE).
6. **Comunicaciones:** notificar a stakeholders internos; si hay datos personales comprometidos, evaluar obligaciones regulatorias (ver sección regulatoria) con revisión jurídica.
7. **Post-incidente:** documentar en `tasks/walkthrough.md` y `memory-bank/progress.md`, actualizar inventario y controles.

**No se prometen RTO/RPO ni alertas operativas no implementadas.** Las alertas actuales se limitan a logs estructurados y eventos en memoria.

## Contexto regulatorio

- **Colombia — Ley 1581 de 2012:** protección de datos personales; autorización del titular y notificación a la SIC ante incidentes que comprometan datos personales, "a la mayor brevedad posible".
- **Florida (EE. UU.) — FIPA:** notificación a afectados y, en ciertos casos, al Attorney General de Florida, dentro de los 30 días posteriores a la detección de una brecha que exponga información personal.
- **Aplicación simultánea:** se considera el régimen más estricto de los dos para componentes que toquen datos de clientes, pagos o empleados.
- **PHI:** Brasaland no trata datos de salud; no se añade HIPAA como requisito genérico.
- **Distinguir:** obligaciones regulatorias (leyes) vs objetivos internos (controles propuestos) vs puntos pendientes de revisión jurídica (plazos exactos, umbrales, definición de brecha). No se inventa un SLA interno.
- **Verificación:** alcance, condiciones y plazos deben verificarse contra fuentes oficiales vigentes; no se copian simplificaciones del BRIEFING como conclusiones legales universales.

## Brechas pendientes y por qué siguen abiertas
1. **Minimo privilegio MCP (G-2/D):** el cliente de prueba tiene 3 scopes; requiere cliente dedicado `incidents:read` y verificación del JWT real. Pendiente de configuración Auth0 (no verificada).
2. **Autorización por location (P-2):** default permisivo hasta que exista allowlist real; decisión de producto pendiente (R-01).
3. **Telemetría pública (R-03):** endpoint sin auth por diseño (no persiste); decisión de producto pendiente.
4. **Dependencias frontend (R-04):** 17 vulnerabilidades; requiere PR dedicado por conflicto de peer deps.
5. **Secretos históricos:** 8 hallazgos en commits antiguos; rotación requiere autorización específica (acción, objetivo, rollback).
6. **Controles de infraestructura:** SSH, firewall, servidor gestionado no verificados.
7. **DAST:** no ejecutado (ZAP no instalado).
8. **Confirmación humana para proveedores (P-5):** implementada para cambio/baja de proveedor (confirmación de un solo uso). Campañas masivas, Brasa Points y pedidos automatizados no existen y se documentan como no implementados (sin crearlos).
9. **Concurrencia multi-proceso:** limitador y memoria son in-memory; documentado como limitación.

## Limitaciones del limitador en memoria
- El rate limiter (`app/common/rate_limit.py`) es por proceso: no compartido entre workers o instancias.
- Si se escala horizontalmente, se requiere un store compartido (p. ej. Redis) — no añadido por no ser necesario en el despliegue actual.
- Deshabilitado automáticamente cuando `BRASALAND_ENV=test`.