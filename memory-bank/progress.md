# Brasaland Progress

## Estado actual
- Contexto de empresa definido y foco validado en pedidos inteligentes de ingredientes.
- Lógica TypeScript del Hito 2 incorporada al branch main (src/types + src/utils).
- Existe una app previa en uis/talent-pipeline-tracker (fuera del alcance funcional directo de este hito).
- Regla de higiene de PR agregada en .agents/rules/pr-hygiene-checklist.md para evitar archivos de ruido.

## En progreso (Milestone 4)
- Configuración de workspaces npm en raíz.
- Creación de infraestructura de agentes (AGENTS.md, .agents/rules, .agents/skills).
- Inicialización de apps Next.js en uis/website, uis/backoffice, uis/loyalty-app, uis/operations-ui.
- Migración de web pública del Hito 1 a uis/website.
- Integración visible de lógica Hito 2 en uis/backoffice.
- Implementación del analizador de incidencias de Brasaland en Python reutilizable para CLI y backend.
- Creación de `services/api` con FastAPI para análisis de CSV y exportación del último resultado.
- Nueva vista `/incidents` en `uis/backoffice` con carga de CSV, resumen operativo y descarga de resultados.

## Próximos pasos inmediatos
1. Ejecutar build completo de backoffice y capturar evidencia visual de la nueva vista de incidencias.
2. Evaluar si el servicio `services/api` debe incorporarse a la orquestación raíz del monorepo.
3. Definir persistencia o histórico si el área operativa necesita conservar múltiples análisis.
4. Implementar protección de rutas completa con cookies HttpOnly para producción.
5. Extender autenticación a otras apps del monorepo (loyalty-app, operations-ui, talent-pipeline-tracker).

## Implementación AUTH-02 (Completada)
- Tipos de autenticación compartidos en `packages/shared/types/auth.ts`.
- Cliente API con manejo de token en `packages/shared/auth/api.ts`.
- Contexto de autenticación con hooks en `packages/shared/auth/context.tsx`.
- Vista de login en `uis/backoffice/src/app/login/page.tsx`.
- Vista de registro en `uis/backoffice/src/app/register/page.tsx`.
- Vista de perfil en `uis/backoffice/src/app/account/profile/page.tsx`.
- Middleware de protección de rutas en `uis/backoffice/src/middleware.ts`.
- Provider de autenticación en `uis/backoffice/src/components/auth-provider.tsx`.
- Layout actualizado con AuthProvider en `uis/backoffice/src/app/layout.tsx`.
- Cliente API helper en `uis/backoffice/src/lib/api.ts`.
- Recuperación de contraseña ajustada para desarrollo local: `POST /auth/forgot-password` ahora devuelve `debug_reset_link` en localhost y la vista `uis/backoffice/src/app/forgot-password/page.tsx` lo muestra para abrir la prueba sin depender de entrega de Resend.
- Flujos `forgot-password`, `reset-password` y `change-password` alineados con pruebas del backend y con actualización segura de tokens TinyDB por query.

## Validaciones ejecutadas
- `python3 /workspaces/campivargas07-ai-engineering-company-project-monorepo/scripts/analyze.py /workspaces/campivargas07-ai-engineering-company-project-monorepo/docs/incidents-brasaland.csv` con conteos esperados: 100 totales, 96 válidos, 4 inválidos y promedio 3.46.
- Exportación interactiva del script con generación de `results.csv`.
- `python3 -m pytest /workspaces/campivargas07-ai-engineering-company-project-monorepo/services/api/tests/test_incidents_api.py` con 3 pruebas verdes.
- `npm --prefix /workspaces/campivargas07-ai-engineering-company-project-monorepo/uis/backoffice run typecheck` exitoso.
- `pytest tests/test_auth_password_reset.py -q` con 13 pruebas verdes.
- `pytest tests/test_auth_change_password.py -q` con 9 pruebas verdes.
- Flujo real validado en localhost: `POST /auth/forgot-password` devuelve `debug_reset_link`, `POST /auth/reset-password` actualiza la contraseña y `POST /auth/login` autentica con la nueva clave.
