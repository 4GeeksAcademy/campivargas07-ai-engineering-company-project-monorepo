# Brasaland Progress

## Hito: Backend de Inventario con ORM y Doble BD (rama `feature/db-inventario`)

- **Fase 0-1**: `docker-compose.yml` (postgres 16, mongo, pgadmin), `.env` raíz,
  modelos SQLAlchemy en `services/backend/app/domains/*` y migración Alembic inicial.
- **Fase 2-3**: API REST con patrón router → service → repository; JWT Bearer en
  escrituras; 28 operaciones / 18 rutas bajo `/api/v1/`; errores de negocio → 400.
- **Fase 4**: seed idempotente (`scripts/seed.py`) — 6 locales, 5 proveedores,
  10 ingredientes, 22 filas de inventario, 15 movimientos, 3 recetas Mongo y 3
  usuarios demo; claves naturales evitan duplicados al re-ejecutar.
- **Fase 5**: suite pytest (23 tests verdes) con PostgreSQL/MongoDB efímeros en
  `tests/conftest.py`; cubre CRUD, transacciones de inventario, kardex, alertas,
  regla moneda-país, borrado lógico y documentos anidados de Mongo.
- **Fase 6**: README del backend con flujo de arranque, tabla de endpoints, reglas
  de negocio y guion del video de 5 min (7 puntos).

## Estado actual
- Contexto de empresa definido y foco validado en pedidos inteligentes de ingredientes.
- Lógica TypeScript del Hito 2 incorporada al branch main (src/types + src/utils).
- Existe una app previa en uis/talent-pipeline-tracker (fuera del alcance funcional directo de este hito).

## Milestone 4 completado
- Workspaces npm configurados en raíz para `uis/*` y `packages/*`.
- Infraestructura AI-ready creada: `AGENTS.md`, `memory-bank/`, `.agents/rules/` y `.agents/skills/`.
- Cuatro apps Next.js operativas en `uis/website`, `uis/backoffice`, `uis/loyalty-app`, `uis/operations-ui`.
- Web corporativa del Hito 1 migrada y funcional en `uis/website` (incluye `/careers`).
- Backoffice integrado con lógica real del Hito 2 mediante imports directos desde `src/utils` y `src/types`.
- Evidencias de entrega generadas en `docs/pr-assets/website-home.png` y `docs/pr-assets/backoffice-hito2.png`.

## Validación ejecutada
1. `npm run typecheck` (root): OK.
2. `npm run typecheck:uis`: OK.
3. `npm run build:uis`: OK.

## Estado de entrega
- Rama de trabajo: `milestone-4`.
- Evidencias preservadas en `docs/pr-assets/` e integración consolidada en `main`.

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

## Hito: Dominio de Inventario en `services/api` (Doble Base de Datos y SQLModel)
- **Doble BD Activa**: TinyDB preservado para usuarios/perfiles/proveedores + PostgreSQL vía SQLModel para catálogo de ingredientes y movimientos de inventario.
- **Stock Dinámico**: `current_stock` nunca persistido en columna; calculado como `SUM(inbound) - SUM(outbound)` por ingrediente y restaurante (`local_id`).
- **Trazabilidad de Identidad**: Toda entrada y salida almacena `user_uuid` estable del usuario TinyDB autenticado (`Depends(get_current_user)`).
- **Control de Concurrencia**: Bloqueo pesimista `SELECT ... FOR UPDATE` a nivel de fila en PostgreSQL para salidas de inventario; rechazo `400 Bad Request` sin persistencia ante saldos insuficientes.
- **Consultas Constantes (Sin N+1)**: Listado de productos y órdenes optimizados mediante consultas de agregación y joins unificados ($O(1)$).
- **Siembra Idempotente**: `seed.py` validando usuario real en TinyDB, sembrando `ING-001` a `ING-007` y movimientos en `MED-001` y `MIA-001` con balance neto idéntico a `src/demo.ts`.
- **Suite de Pruebas**: 65 pruebas automatizadas pasando al 100% (unitarias en SQLite aislado y de integración/concurrencia en PostgreSQL con `TEST_DATABASE_URL`), con 94% de cobertura en `app.domains.operations.inventory`.

## Hito 5: Backoffice de Gestión de Inventario (`uis/backoffice`, rama `feature/backoffice-inventario`)
- **Capa API Normalizada**: `src/lib/inventory.ts` centralizando llamadas hacia `services/api` (`/inventory/*`), construcción segura de URLs sin doble slash, `URLSearchParams`, inyección de `Authorization: Bearer <token>`, parseo robusto de respuestas no-JSON, formateo de validaciones 422 de Pydantic y logout limpio desacoplado ante 401 sin fugar tokens en consola.
- **Configuración Temporal de Locales**: `src/lib/constants/restaurants.ts` restringido a las sedes con datos activos en el seed del backend (`MED-001` y `MIA-001`), documentado como módulo temporal y protegido con fallbacks para identificadores arbitrarios devueltos por la API.
- **Rutas y Navegación Limpias**: Eliminado el rewrite confuso `/inventory/:path*` de `next.config.ts`. Todas las páginas y enlaces de frontend residen exclusivamente bajo `/backoffice/inventory/*`.
- **Actualización Dinámica e Inmediata de Stock**:
  - `InboundOrderForm`: incremento reactivo e inmediato del stock en memoria tras HTTP 201, reseteo de input de cantidad y mensaje de éxito persistente con botón de descarte.
  - `OutboundOrderForm`: consulta reactiva con estado de carga ("Consultando..."), cancelación de peticiones desfasadas, bloqueo preventivo del botón de envío si la cantidad supera el stock disponible, captura inline del `HTTP 400 InsufficientStockError` junto al input de cantidad y decremento inmediato del saldo en memoria tras HTTP 201.
- **Experiencia de Usuario y Accesibilidad**:
  - Semáforos textuales normalizados: `Agotado` ($\le 0$), `Stock bajo` ($\le min$), `Saludable` ($> min$).
  - Historial `OrdersLedger` con badges textuales legibles (`📥 ENTRADA` / `📤 SALIDA`), sede descriptiva (`nombre (id)`), fecha localizada `DD/MM/YYYY HH:mm` y `user_uuid`.
  - Manejo completo de estados en todas las vistas: carga accesible, error con botón de `Reintentar` y estado vacío con botones de llamada a la acción (CTA).
- **Protección de Rutas sin Destello**: `AuthGuard` bloqueando el render de componentes protegidos mientras el estado de autenticación no esté confirmado, redirigiendo a `/login` a usuarios anónimos.
- **Suite de Pruebas y Calidad de Código**:
  - `TEST_DATABASE_URL=... uv run --directory services/api pytest`: 65 pruebas pasando al 100% (0 omitidas, 0 fallos).
  - `npm --prefix uis/backoffice run test`: 39 pruebas verdes en 8 suites (incluyendo precedencia de URL, incremento/decremento de stock y fallback de reconciliación).
  - `npm --prefix uis/backoffice run typecheck`: 0 errores TypeScript.
  - `npm --prefix uis/backoffice run lint`: 0 errores, 0 advertencias ESLint.
  - `npm --prefix uis/backoffice run build`: compilación de producción exitosa (10/10 rutas estáticas prerenderizadas con Next.js 16 y Turbopack).
  - `npm run test:uis`: 43 pruebas verdes en el monorepo (39 backoffice + 4 website).
- **Estado de la Verificación Visual**: Marcada como pendiente de inspección manual por el usuario en navegador real (el entorno de ejecución carece de binarios de navegadores para automatización).
- **Estado de Integración con PR #8**: Pendiente de resolución de divergencias en `src/lib/auth/api.ts` y `src/app/login/page.tsx` al momento de fusionar ramas.
- **Higiene de Repositorio**: Limpieza estricta de artefactos (`.env.local`, `__pycache__`, `.coverage`) y restauración de `services/api/data/suppliers.json` al estado limpio original (sin usuarios demo ni hashes).

## Hito de Infraestructura: Dockerizar el Entorno Completo de Desarrollo
- **Orquestación en Raíz (`docker-compose.yml`)**:
  - Exactamente dos servicios definidos: `interfaces` (Website + Backoffice en un solo contenedor) y `backend` (`services/api` con FastAPI).
  - Red dedicada tipo bridge `brasaland-dev`.
  - Bind mounts de desarrollo (`./uis:/app`, `./services:/app`) con volúmenes anónimos para preservar `node_modules` y directorios de compilación (`.next`).
  - Configuración estricta por variables de entorno sin secretos versionados; Compose configurado con sustitución obligatoria `${DATABASE_URL:?DATABASE_URL is required}` y `${SECRET_KEY:?SECRET_KEY is required}`.
- **Contenerización de Interfaces (`uis/Dockerfile`, `uis/start.sh`, `uis/.dockerignore`)**:
  - Imagen base `node:22-alpine` con usuario no-root `node`.
  - Instalación limpia con `npm ci` (o fallback resiliente `npm install --legacy-peer-deps`).
  - Contexto optimizado con `**/node_modules` y `**/.next` reduciendo la transferencia a <10 KB.
  - Script supervisor `uis/start.sh` en POSIX `/bin/sh` con manejo de señales `SIGINT`/`SIGTERM`, monitoreo concurrente y Next.js dev server con `--webpack` para resolución de módulos del monorepo (`externalDir`).
- **Contenerización de Backend (`services/Dockerfile`, `services/.dockerignore`)**:
  - Imagen base `python:3.12-slim` con usuario no-root `appuser`.
  - Entorno virtual aislado en `/opt/venv` garantizando que los bind mounts del host no sobrescriban ni corrompan las dependencias.
  - Gestión rápida y determinista de dependencias con `uv sync --active --frozen --no-dev`.
  - `WORKDIR /app/api` respetando la ubicación real de `pyproject.toml` y `uv.lock`.
  - Preservación íntegra de `services/api/data/suppliers.json` (TinyDB) sin duplicaciones ni movimientos.
- **Resolución Interna y Proxies**:
  - Configuración de `uis/backoffice/next.config.ts` para reescribir `/api/:path*` dinámicamente hacia `process.env.INTERNAL_API_URL` (valor en Compose: `http://backend:8000`).
  - Suite Vitest (`uis/backoffice/src/test/next-config-rewrites.test.ts`) validando al 100% el comportamiento de rewrites y sanitización de URLs.
  - Validación de conectividad inter-contenedor: `curl http://backend:8000/health` desde `interfaces` respondiendo `{"status":"ok"}`.
- **Recarga en Caliente (Hot Reload)**:
  - Verificado en Website (`uis/website/src/app/page.tsx`), Backoffice (`uis/backoffice/src/app/page.tsx`) y FastAPI (`services/api/app/main.py`).
  - Recompilación instantánea sin reconstrucción de contenedores.
  - Árbol de trabajo Git restaurado al 100% de limpieza tras pruebas.
- **Calidad y Verificación**:
  - `npm run test:uis`: 46/46 pruebas pasando (42 en backoffice, 4 en website).
  - `npm --prefix uis/website run typecheck && lint && build`: 5/5 páginas estáticas prerenderizadas.
  - `npm --prefix uis/backoffice run typecheck && lint && build`: 10/10 páginas estáticas prerenderizadas.
  - Backend Pytest: 65/65 pruebas pasando contra PostgreSQL (`TEST_DATABASE_URL`).
  - Documentación de inicio, puertos y parada segura en `README.md` y `README.es.md`.

## Mantenimiento y Optimización de Entorno (GitHub Codespaces)
- **Remediación de Espacio Crítico (<1% restante)**:
  - Recuperados **~12.5 GB** de almacenamiento (reduciendo el uso de 100% a 59%, dejando ~13 GB disponibles).
  - Purgado seguro de caché BuildKit de Docker (`3.54 GB`), volúmenes anónimos huérfanos (`3.78 GB`) y contenedor huérfano (`amazing_keller`).
  - Limpieza de cachés globales de usuario: Playwright Chromium (`656 MB`), NPM cache (`1.0 GB`), uv y pip (`~180 MB`).
  - Deduplicación y consolidación de dependencias del monorepo en `node_modules` raíz de npm workspaces.
  - Limpieza de artefactos transitorios de compilación (`uis/*/.next`) y cachés de Python (`.pytest_cache`, `__pycache__`).
  - **Preservación Estricta de PRs y Datos**: Bases de datos PostgreSQL y MongoDB (`brasaland_brasaland_pgdata`, `brasaland_brasaland_mongodata`), archivos `.env` y TinyDB intactos. Cero modificaciones a ramas de Pull Requests abiertas.
  - Script automatizado preventivo incorporado en `scripts/clean-env.sh`.
  - Verificación de integridad: `npm run test:uis` (46/46 pruebas verdes) y `npm run typecheck:uis` (0 errores).

## Corrección de Autenticación Previa en Backoffice
- **Feedback atendido**: El backoffice ya no expone el resumen operativo al abrir la app sin autenticación. La ruta pública `/` redirige a `/login` sin renderizar KPIs, ventas, alertas de stock ni navegación interna.
- **Rutas internas protegidas**: Resumen movido a `/backoffice/overview`; incidencias movidas a `/backoffice/incidents`; inventario mantiene `/backoffice/inventory/*`.
- **Sin destello de consola interna**: `AuthGuard` envuelve el header y contenido completo de Resumen, Incidencias e Inventario antes de renderizar datos o navegación.
- **Navegación adaptada**: `BackofficeHeader` apunta solo a rutas internas protegidas y el login exitoso redirige al resumen autenticado.
- **Compatibilidad**: `/incidents` se conserva como redirección a `/backoffice/incidents` sin mostrar el analizador públicamente.
- **Calidad adicional**: Corregidos dos avisos de lint React hooks en filtros de inventario (`ProductsTable` y `OrdersLedger`) para mantener una validación limpia.
- **Validaciones ejecutadas**:
  - `npm --prefix uis/backoffice run test`: 49/49 pruebas pasando en 10 suites.
  - `npm --prefix uis/backoffice run typecheck`: 0 errores TypeScript.
  - `npm --prefix uis/backoffice run lint`: 0 errores ESLint.
  - `npm --prefix uis/backoffice run build`: build exitoso tras apartar un artefacto `.next` previo con ownership `root:root`.

## Auditoría de Rendimiento Frontend

- **Cobertura:** Lighthouse 13.4.1 en builds de producción para Website `/` y
  `/careers`, y Backoffice autenticado `/backoffice/overview`, en móvil y
  escritorio. Se versionaron reportes HTML/JSON y capturas antes/después.
- **Mejora principal:** Backoffice móvil pasó de Performance 73 a 85, LCP 2,4 s
  a 1,5 s y TBT 1.310 ms a 580 ms. El trabajo de hilo principal bajó de 2,9 s a
  1,6 s, el arranque JS de 1,8 s a 0,9 s y las tareas largas de 12 a 5.
- **Hidratación:** `AuthProvider` inicia de forma determinista en SSR y cliente;
  la sesión se resuelve tras el montaje. Eliminado React #418 y Best Practices
  queda en 100.
- **Imágenes:** hero, menú y collage migrados de fondos remotos a `next/image`
  con WebP locales, `sizes` y prioridad explícita para el LCP. Home móvil final:
  Performance 98, LCP 1,1 s y TBT 160 ms.
- **Accesibilidad:** corregidos contraste de CTA y orden de encabezados en ambas
  interfaces. Las seis mediciones finales quedan en Accessibility 100.
- **Reutilización:** nuevo `RestaurantSelect` integrado en productos y órdenes,
  sin mover filtrado, persistencia ni reglas de dominio al componente.
- **Validaciones:** `npm run test:uis` con 58/58 pruebas; `npm run typecheck:uis`,
  lint de Website y Backoffice, y builds de producción de ambas apps sin errores.
  Verificación final en navegador sin errores de página.
- **Documentación:** diagnóstico en `AUDIT.md`, comparativa en `REPORT.md` y
  evidencia completa en `audit/before/` y `audit/after/`.

## Integración PR #10: Gestor de Incidentes

- **Conflictos resueltos:** se conservó el analizador CSV ya integrado en
  `app.domains.analytics.incidents` y se añadió el dominio CRUD independiente
  `app.domains.incidents`, registrando primero las rutas estáticas de análisis
  para evitar colisiones con `/{incident_id}`.
- **Persistencia segura:** el repositorio TinyDB abre su archivo de producción
  de forma diferida; las pruebas inyectan una tabla temporal y no crean ni
  modifican datos reales del repositorio.
- **Contrato compartido:** tipos, etiquetas y transiciones de incidencias viven
  en `packages/shared`; el backoffice consume el paquete en vez de duplicar el
  modelo de dominio.
- **Backoffice protegido:** `/backoffice/incidents` integra tablero, alta,
  filtros, resumen, transiciones de estado y el analizador CSV existente bajo
  `AuthGuard`. `/incidents` continúa siendo sólo una redirección.
- **Compatibilidad de pruebas:** se agregó `httpx2` al grupo de desarrollo,
  requerido por el `TestClient` de Starlette 1.6, y se impidió que una variable
  `DATABASE_URL` local conecte las pruebas unitarias a recursos externos.
- **Validación:** 77 pruebas backend verdes y 5 integraciones PostgreSQL
  omitidas sin `TEST_DATABASE_URL`; 65 pruebas frontend, typecheck y lint sin
  errores; build de producción exitoso con 16 rutas estáticas.
- **Higiene:** se excluyeron `.env`, archivos TinyDB locales, bytecode,
  cobertura y metadatos generados. Las PR #15 y #16 permanecen intactas.
