# Brasaland Progress

## Estado actual
- Contexto de empresa definido y foco validado en pedidos inteligentes de ingredientes.
- Lógica TypeScript del Hito 2 incorporada al branch main (src/types + src/utils).
- Existe una app previa en uis/talent-pipeline-tracker (fuera del alcance funcional directo de este hito).
- Regla de higiene de PR agregada en .agents/rules/pr-hygiene-checklist.md para evitar archivos de ruido.

## En progreso (Milestone 4 / AUTH-02)
- Configuración de workspaces npm en raíz.
- Creación de infraestructura de agentes (AGENTS.md, .agents/rules, .agents/skills).
- Inicialización de apps Next.js en uis/website, uis/backoffice, uis/loyalty-app, uis/operations-ui.
- Migración de web pública del Hito 1 a uis/website.
- Integración visible de lógica Hito 2 en uis/backoffice.
- Implementación del analizador de incidencias de Brasaland en Python reutilizable para CLI y backend.
- Creación de `services/api` con FastAPI para análisis de CSV y exportación del último resultado.
- Nueva vista `/incidents` en `uis/backoffice` con carga de CSV, resumen operativo y descarga de resultados.

## Implementación AUTH-02 y Correcciones de Feedback
- Plantillas `.env.example` añadidas en raíz, `services/api/`, `uis/backoffice/`, `uis/website/`, `uis/loyalty-app/`, `uis/operations-ui/`.
- Navegación mejorada en `BackofficeHeader` con botones visibles para Iniciar Sesión (`/login`), Registrarse (`/register`), Perfil (`/account/profile`) y Cerrar Sesión.
- Corrección de rol en registro (`role: 'admin'`) en frontend (`uis/backoffice` y `packages/shared`) y backend (`UserRole` en `services/api`).
- Instrucciones detalladas de despliegue y ejecución local añadidas a `README.md` y `README.es.md`.
- Backend FastAPI actualizado con `requirements.txt`, soporte CORS para todos los puertos locales, router de incidencias y suite de tests completa (`pytest`).

## Validaciones ejecutadas
- `python3 /workspaces/campivargas07-ai-engineering-company-project-monorepo/scripts/analyze.py /workspaces/campivargas07-ai-engineering-company-project-monorepo/docs/incidents-brasaland.csv` (100 totales, 96 válidos, 4 inválidos).
- `python3 -m pytest services/api/tests` con 6 pruebas verdes al 100% (incidents + auth API).
- `npm run typecheck:uis` exitoso en las 4 aplicaciones de Next.js.
- `npm run build:uis` exitoso en website, backoffice, loyalty-app y operations-ui.
