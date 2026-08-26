# Brasaland Progress

## Estado actual
- Contexto de empresa definido y foco validado en pedidos inteligentes de ingredientes.
- Lógica TypeScript del Hito 2 incorporada al branch main (src/types + src/utils).
- Existe una app previa en uis/talent-pipeline-tracker (fuera del alcance funcional directo de este hito).

## En progreso (Milestone 4 / AUTH-088)
- Configuración de workspaces npm en raíz.
- Creación de infraestructura de agentes (AGENTS.md, .agents/rules, .agents/skills).
- Inicialización de apps Next.js en uis/website, uis/backoffice, uis/loyalty-app, uis/operations-ui.
- Migración de web pública del Hito 1 a uis/website.
- Integración visible de lógica Hito 2 en uis/backoffice.
- Implementación del analizador de incidencias de Brasaland en Python reutilizable para CLI y backend.
- Creación de `services/api` con FastAPI para análisis de CSV y exportación del último resultado.
- Nueva vista `/incidents` en `uis/backoffice` con carga de CSV, resumen operativo y descarga de resultados.
- **AUTH-088**: Cobertura de pruebas unitarias para la API de autenticación completada al 100% en `app.domains.auth` (45 pruebas backend pasando, aislamiento de TinyDB, protección de datos reales y documentación en `TESTING.md`).
- **Actividad Extra (Testing UI)**: Batería de pruebas unitarias y de integración de frontend implementada con Vitest y React Testing Library en `uis/backoffice` (10 pruebas) y `uis/website` (4 pruebas), todas 100% verdes.

## Próximos pasos inmediatos
1. Ejecutar build completo de backoffice y capturar evidencia visual de la nueva vista de incidencias.
2. Evaluar si el servicio `services/api` debe incorporarse a la orquestación raíz del monorepo.
3. Definir persistencia o histórico si el área operativa necesita conservar múltiples análisis.
4. Revisar con producto la política de auto-asignación de roles en el registro público (`POST /users`).

## Validaciones ejecutadas
- `python3 /workspaces/campivargas07-ai-engineering-company-project-monorepo/scripts/analyze.py /workspaces/campivargas07-ai-engineering-company-project-monorepo/docs/incidents-brasaland.csv` con conteos esperados: 100 totales, 96 válidos, 4 inválidos y promedio 3.46.
- Exportación interactiva del script con generación de `results.csv`.
- `uv run pytest --cov=app.domains.auth --cov-report=term-missing --cov-fail-under=70` en `services/api` con 45 pruebas verdes y 100% de cobertura en `app.domains.auth`.
- Verificación de aislamiento estricto de TinyDB (sin modificaciones en `services/data/suppliers.json`).
- `npm run test:uis` en raíz con 14 pruebas de frontend/backoffice verdes (10 en backoffice, 4 en website).
