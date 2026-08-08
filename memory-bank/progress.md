# Brasaland Progress

## Estado actual
- Contexto de empresa definido y foco validado en pedidos inteligentes de ingredientes.
- Lógica TypeScript del Hito 2 incorporada al branch main (src/types + src/utils).
- Existe una app previa en uis/talent-pipeline-tracker (fuera del alcance funcional directo de este hito).
- **Supplier Directory implementado y funcional** (backend + frontend completo).

## En progreso (Milestone 4)
- Configuración de workspaces npm en raíz.
- Creación de infraestructura de agentes (AGENTS.md, .agents/rules, .agents/skills).
- Inicialización de apps Next.js en uis/website, uis/backoffice, uis/loyalty-app, uis/operations-ui.
- Migración de web pública del Hito 1 a uis/website.
- Integración visible de lógica Hito 2 en uis/backoffice.
- Implementación del analizador de incidencias de Brasaland en Python reutilizable para CLI y backend.
- Creación de `services/api` con FastAPI para análisis de CSV y exportación del último resultado.
- Nueva vista `/incidents` en `uis/backoffice` con carga de CSV, resumen operativo y descarga de resultados.
- **Supplier Directory** (`/suppliers`): directorio CRUD de proveedores con TinyDB + Pydantic + Next.js.

## Completado recientemente — Supplier Directory

### Backend (services/api)
- **database.py**: TinyDB centralizado con `SUPPLIERS_DB_PATH` env-var para aislamiento de tests.
- **schemas.py**: 7 modelos Pydantic (`SupplierCreate`, `SupplierRateUpdate`, `SupplierStatusUpdate`, `SupplierResponse`, `SupplierListResponse`) + 3 enums (`Pais`, `Moneda`, `CategoriaIngrediente`, `SupplierStatus`).
- **service.py**: 7 funciones CRUD (create, list, get, update_rate, update_status, delete) con TinyDB Query-based lookups.
- **router.py**: 6 endpoints REST: POST /api/suppliers (201), GET /api/suppliers (filtros), GET /api/suppliers/{id}, PATCH rate, PATCH status, DELETE (404s).
- **main.py**: Router registrado con prefijo `/api/suppliers`.
- **seed.py**: Seeder idempotente con 3 proveedores iniciales (Avícola Valle, Bogotá Meats, SaludPack). Comando validado: `uv run seed`.
- **pyproject.toml**: tinydb, httpx2 (dev) añadidos. Package find config para `app*`.
- **tests/test_suppliers_api.py**: 22 tests verdes cubriendo todos los endpoints + validación + edge cases.
- **Compatibilidad de entrega**: añadidos `services/api/main.py`, `services/api/models.py`, `services/api/database.py` y `services/api/routes/suppliers.py` como wrappers para cumplir la estructura solicitada sin mover la arquitectura base.

### Frontend (uis/backoffice)
- **lib/suppliers-api.ts**: API client con funciones `listSuppliers`, `createSupplier`, `updateSupplierRate`, `updateSupplierStatus`, `deleteSupplier`.
- **components/suppliers-directory.tsx**: Componente completo con: tabla de proveedores, filtros país/categoría, formulario de creación inline, edición de tarifa inline, toggle de estado (activo/suspendido), métricas hero (total/activos/suspendidos).
- **app/suppliers/page.tsx**: Page wrapper con layout backoffice.
- **components/backoffice-header.tsx**: Nav extendido con link "Proveedores" → `/suppliers`.
- **app/globals.css**: Estilos CSS para supplier directory (hero, filtros, tabla, chips, formularios, inline edit).
- **Compatibilidad de entrega**: añadida ruta espejo en `uis/application/app/suppliers/page.tsx` y documentación en `uis/application/README.md`.

## Próximos pasos inmediatos
1. Ejecutar build completo de backoffice y capturar evidencia visual de la nueva vista de proveedores.
2. Evaluar si el servicio `services/api` debe incorporarse a la orquestación raíz del monorepo.
3. Definir persistencia o histórico si el área operativa necesita conservar múltiples análisis.
4. Completar funcionalidad de eliminación de proveedores con confirmación en UI.

## Validaciones ejecutadas
- `python3 /workspaces/campivargas07-ai-engineering-company-project-monorepo/scripts/analyze.py /workspaces/campivargas07-ai-engineering-company-project-monorepo/docs/incidents-brasaland.csv` con conteos esperados: 100 totales, 96 válidos, 4 inválidos y promedio 3.46.
- Exportación interactiva del script con generación de `results.csv`.
- `python3 -m pytest /workspaces/campivargas07-ai-engineering-company-project-monorepo/services/api/tests/test_incidents_api.py` con 3 pruebas verdes.
- `uv run pytest tests/test_suppliers_api.py -v` → 22 tests verdes.
- `uv run seed` → 0 inserted, 3 skipped (idempotente), total en base: 3.
- `npm --prefix /workspaces/campivargas07-ai-engineering-company-project-monorepo/uis/backoffice run typecheck` exitoso.
