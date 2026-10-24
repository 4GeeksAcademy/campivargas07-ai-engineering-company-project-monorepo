# Hito: Agente de Soporte con LangGraph — Parte 2: Herramientas Fuera del RAG (23-oct-2026)

- Se inicia en `feature/langgraph-external-tools`, creada desde
  `origin/main` (`7327ea61c43a5f2333e502341989bc62890f3a6b`, Parte 1 integrada).
  La rama anterior, los stashes y las PR previas no se modifican.
- Se añade una herramienta HTTP tipada de sólo lectura al gestor real:
  `GET /api/incidents` y `GET /api/incidents/{incident_id}`. Usa
  `INCIDENTS_SERVICE_URL`, timeout `5.0s` y reenvía el Bearer ya validado por
  `get_current_user`, que el backend de incidentes vuelve a validar. No hay
  token de servicio hardcodeado ni credenciales en estado/checkpoints/traces.
- El grafo existente decide entre RAG, incidencias, ambas fuentes o pedir un
  ID interno válido. Los fallbacks para timeout, permisos, no encontrado y
  servicio no disponible no consultan RAG ni inventan estados. Las preguntas
  combinadas presentan respuestas separadas. Los campos libres `title` y
  `description` se descartan como contenido no confiable.
- Los traces nuevos omiten el texto de la pregunta y los IDs operativos;
  registran fuente, nodos, resultado categórico y fallback. Se documenta el
  diseño y los comandos en `docs/rag/langgraph-agent-part2.md`.
- Verificación dirigida: 94 pruebas pasan (`test_agent_evals.py`, `test_rag.py`
  y `services/api/tests/test_agent_api.py`) con pytest. Se instaló el entorno
  temporal fuera del checkout en `/tmp/brasaland-agent-part2-venv`; no se
  modificaron manifiestos.
- La validación real y export de traces no pudo ejecutarse: faltan
  `INCIDENTS_SERVICE_URL`, token y configuración RAG; el API no escucha en
  `localhost:8000`. Qdrant responde en `localhost:6333`, lo que no basta para
  validar consultas reales de ninguna de las dos fuentes. No se presentan los
  mocks de pruebas como integración.
- Después de las pruebas apareció `data/suppliers.json` como ruta no versionada.
  La política de exclusión bloqueó su inspección; se dejó intacta y no se
  intentó acceder por otra vía. No se hizo commit, push ni PR.
- Seguimiento (24-oct-2026): el usuario solicitó publicar la rama con traces
  de incidencias y RAG y resultados de evals. Se confirmó **94 passed** en la
  suite dirigida, incluyendo nuevos evals con mocks; no demuestra integración
  real. No hay servicios/credenciales para generar traces reales. La política
  de exclusión también bloqueó la lectura de archivos de traces bajo
  `data/eval/`, por lo que no se intentaron rutas alternativas ni se adjuntan.
- La rama aún no está publicada: `gh auth status` indica que no hay sesión y
  `git push --dry-run` falla por falta de credenciales. No se creó una PR ni se
  aplicó etiqueta. Se requiere restaurar acceso a GitHub y proporcionar/autorizar
  evidencias de trace accesibles para completar la entrega solicitada.

# Preparación de PR borrador RAG — 16 de octubre de 2026

- El usuario solicitó publicar una PR con el trabajo, las complicaciones y los
  pendientes. Se prepara commit y push en `feature/rag-knowledge-base-restart`
  hacia `main`, en modo Draft y sin merge ni declaración de cierre del hito.
- La descripción debe distinguir la evidencia offline comprobada de las
  validaciones reales pendientes, y documentar la exclusión de `data/`, la
  diferencia k=3/k=5 del evaluador y los errores previos reproducidos.
- Se excluye del commit el cambio ajeno de whitespace en
  `services/.dockerignore`. Las notas históricas de ausencia de commit/PR
  corresponden a las ejecuciones anteriores, no a esta solicitud de publicación.

# Continuación RAG autorizada — 16 de octubre de 2026

- Se confirmó con Git que `HEAD` y `main` apuntan a
  `f18688e583aba6d912e4a887b17ec3baf2dd0806`, en
  `feature/rag-knowledge-base-restart`. Se preservó la implementación local sin
  commit; no se recuperaron ramas, commits ni stashes retirados.
- Se ampliaron pruebas de umbral inclusivo de `retrieve`, rechazo de tokens
  inválidos/usuarios inactivos antes de generar, sesión ausente, contrato de
  respuesta y propagación de cancelación del cliente HTTP.
- Evidencia nueva: baseline extraído del commit autorizado, API 129 passed/5
  skipped y Backoffice 89/Website 4. Checkout: pipeline 47 passed, API 142
  passed/5 skipped (189 passed combinados); Backoffice 107/Website 4. PostgreSQL
  real sigue sin probar por ausencia de `TEST_DATABASE_URL`.
- Typecheck y lint reproducen exactamente los tres errores TypeScript y los dos
  errores ESLint de auth/telemetría del baseline. El build actual compila y luego
  falla en `AuthMeResponse.id`, también reproducido en el baseline con Webpack;
  no se atribuye a esta sesión el antiguo fallo de Google Fonts. Lint dirigido
  del slice RAG y `docker compose config --quiet` pasan.
- Pendiente detectado: `data/eval/run.py` genera con contexto `k=3`; debe medir
  Recall@3 por separado y generar/registrar el contexto `k=5` usado en producción.
  La exclusión de Copilot bloqueó la edición de `data/`; la corrección no se
  aplicó. El usuario no estaba disponible para habilitar acceso. No se declara
  cerrado el hito ni se considera validada la fidelidad del recorrido real.
- El acceso/contrato y modelos de 4Geeks siguen sin confirmar. No se solicitaron
  credenciales ni se invocaron proveedores reales. No se instalaron dependencias,
  iniciaron contenedores, cambiaron ramas ni hicieron commit, push o PR.
- Se restauró sólo bytecode versionado generado por estas pruebas, limpio al
  inicio. Se preservó un cambio concurrente ajeno en `services/.dockerignore`
  que hace fallar el chequeo global de whitespace.

# Reinicio del hito RAG — 15 de octubre de 2026

- El usuario autorizó retirar la implementación RAG y publicar una PR de reversión para reiniciar el hito con un prompt nuevo.
- Rama de retirada: `chore/revert-rag-for-restart`, creada desde `origin/main` en `adc9115` mediante worktree aislado. Se revierten `adc9115`, `4ccc89b` y `e685b60` sin reset ni force push; el historial anterior permanece recuperable.
- Se retiran corpus/contexto/planes del RAG anterior, pipeline, endpoint Knowledge, pantalla/cliente/pruebas específicas, servicio/configuración Qdrant y dependencia añadida. El código funcional vuelve a la base `810a873`; se conserva el resto de Brasaland y el historial de sus hitos. Sólo se normalizó una línea vacía final de Dockerfile para el chequeo de whitespace.
- No se modifican los stashes, la rama RAG antigua, datos TinyDB, bases ni volúmenes Docker. No se aplican pruebas antiguas como evidencia nueva.
- Validación de esta retirada: API 129 passed/5 skipped (PostgreSQL sin `TEST_DATABASE_URL`); Compose config válido. Backoffice 89 passed/16 suites; typecheck conserva tres errores del baseline y build falla por descarga de Google Fonts. Whitespace y alcance verificados.
- La PR debe fusionarse antes de iniciar el nuevo RAG desde `main` actualizado. No reutilizar `feature/rag-knowledge-base`, que apunta a una rama antigua con otros hitos y upstream de regresión. Crear una rama nueva para el nuevo intento.

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

## Hito: Optimización de rendimiento — Lazy Loading, useMemo y caché TTL (rama `feature/caching-optimisation`)

- **Fase 0 (línea base)**: registrada antes de tocar código — pytest 64 passed/5 skipped;
  backoffice: typecheck PASS, vitest 54 tests, build PASS; JS inicial de
  `/backoffice/incidents` = 644 997 bytes (9 chunks). Fallos preexistentes: ninguno.
- **Fase 1 (timing)**: `app/common/timing.py` — middleware ASGI que registra
  `método ruta → status (ms)` con `time.perf_counter()`, sin query strings/headers
  (sin datos sensibles); cableado en `app/main.py` antes de CORS.
- **Fase 2 (lazy loading)**: 2 niveles con `next/dynamic` — página server
  (`incidents/page.tsx`) → `IncidentsAnalyzer`, y el analizador → nuevo
  `IncidentsResults` (panel completo de tablas/KPIs) con fallback `loading` y sin
  `ssr:false`. El panel queda en chunk propio (`1f6cd-uud07yr.js`, 6 830 B) fuera del
  HTML/RSC inicial; payload inicial casi sin cambio (644 070 B) porque domina el shell.
- **Fase 3 (useMemo)**: `src/lib/incidents-derive.ts` (derivación pura: ranking
  consolidado de 4 tablas con % por tabla y % acumulado, Pareto 80 %, códigos únicos)
  memoizada en `IncidentsResults` con `useMemo([analysis])`; 10 tests unitarios.
- **Fase 4 (caché TTL)**: `app/common/cache.py` — `TTLCache` stdlib-only: claves
  deterministas (`build_key` + `normalize_filter`), TTL por entrada, expiración con
  reloj monotónico inyectable, LRU con `max_size=256`, copias profundas de valores,
  estadísticas (hits/misses/evictions/expired/size/hit_rate) y logs `brasaland.cache`.
  En suppliers: listas TTL 60 s, detalle TTL 120 s, 404 nunca cacheado, y
  POST/rate/status/delete invalidan por prefijo `suppliers:` (lista + todas las
  variantes + detalle).
- **Fase 5 (tests backend)**: `tests/test_suppliers_cache.py` — 22 tests: MISS→HIT,
  variantes de filtros → claves distintas, expiración con reloj inyectado (sin sleeps),
  invalidación tras cada escritura, 404 sin cachear, copias defensivas, eviction LRU,
  ttl<=0, sanity de TTLs y middleware de timing (estado/cuerpo intactos + regex del
  formato de log + sin fuga de password/Authorization).
- **Fase 6 (medición)**: dataset de 5 000 proveedores en `/tmp/brasa-seed/` generado
  con `scripts/seed_suppliers.py` (nunca toca `services/api/data/`); escenario
  cold/warm/invalidación/expiración (n=25 por variante) con
  `scripts/measure_cache.py`. Detalle: 2.2→1.5 ms mediana (−32 %). En listas domina la
  serialización/transporte de ~2 MB (HIT ≈ MISS en mediana; el cache elimina consulta
  TinyDB y refiltrado). Expiración de 60/120 s observada en tiempo real con logs
  EXPIRED. Detalle completo en `CACHING_REPORT.md`.
- **Verificación final**: pytest 86 passed/5 skipped (+22 tests); typecheck:uis PASS;
  test:uis 64+4 passed; lint backoffice PASS; build:uis 4/4 PASS.

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

## Implementación: Auditoría de serialización del backend (`feature/serialization-audit`)

- **Alcance confirmado:** `services/api` es el backend activo; `services/backend`
  permanece fuera de alcance por pertenecer a un hito anterior.
- **Contratos añadidos:** `HealthResponse` para `GET /health` y `DeleteResponse`
  para `DELETE /users/{user_id}` y `DELETE /api/suppliers/{supplier_id}`.
- **Seguridad:** se conservan respuestas de usuarios sin `password` ni
  `hashed_password`; el JWT de login sigue siendo el único token contractual
  expuesto. Se conserva `user_uuid` en movimientos por trazabilidad del ledger.
- **Frontend:** `AuthMeResponse` en `uis/backoffice` se alineó con la respuesta
  anidada `{ user, profile }` del backend.
- **Pruebas agregadas:** `services/api/tests/test_serialization_contracts.py`
  cubre health, filtrado de hashes, borrado y presencia de modelos en OpenAPI.
- **Auditoría:** creada `docs/serialization-audit.md`, conservando diagnóstico
  inicial, estado final, contratos especiales, riesgos y validaciones pendientes.
- **Estado:** implementación funcional aplicada; pruebas completas, typecheck,
  lint y verificación manual mediante `/docs` quedan pendientes de ejecución.

## Revisión de comentarios PR #15: contratos de registro y CSV
- **Autorregistro seguro:** `UserCreate` ya no admite `role` y rechaza campos extra; el servicio fija `user` desde servidor. Las cuentas privilegiadas deben asignarse desde una ruta autenticada con autorización administrativa.
- **Minimización de datos:** `POST /users` devuelve `UserRegistrationResponse` (`detail`, `id`) sin email ni rol. Backoffice ya no envía ni tipa un rol al registrar y posteriormente inicia sesión con las credenciales del formulario.
- **OpenAPI CSV:** `GET /api/incidents/results/export` declara `text/csv`, contenido binario, `Content-Disposition` y error 404, sin cambiar la descarga CSV.
- **Regresión:** pruebas cubren rechazo de `role`, rol asignado por servidor, respuesta sin email, contrato OpenAPI y cabeceras reales CSV.
- **Validación:** `uv run --directory services/api pytest`: 67 passed, 5 skipped (integraciones PostgreSQL sin entorno). Typecheck frontend pendiente de sanear `.next/types` obsoleto, que referencia páginas inexistentes en este checkout; no reportó errores en el código auth actualizado.

## Resolución de conflictos del merge de `main` en PR #15
- Se conservaron en la misma integración los cambios de serialización/seguridad de PR #15 y los dominios de incidentes y recuperación de contraseña ya presentes en `main`.
- `GET /health` mantiene `HealthResponse`; la API del backoffice incluye tipos y métodos de cambio/recuperación de contraseña, y el registro continúa sin aceptar `role`.
- Se corrigió la página de perfil para leer `user.email`, `user.role` y `user.is_active` desde la respuesta anidada real de `/auth/me`.
- Se eliminaron los marcadores literales de conflicto en cinco archivos y se preservaron las dos series de documentación histórica.
- **Validación del merge:** API 91 passed, 5 skipped; backoffice 67 tests y lint sin errores. Typecheck ya no reporta errores de código: persisten dos referencias antiguas bajo `.next/types/validator.ts` a páginas que no existen en este checkout.

## Revisión de comentarios PR #16 — caché y conflictos de `main`
- **Conflictos integrados:** `services/api/app/main.py` conserva `RequestTimingMiddleware` y `register_incident_error_handlers`; la ruta de incidencias usa `IncidentBoard` de `main` y el analizador CSV se separó como chunk dinámico dentro de la pestaña de análisis.
- **Race de invalidación:** `TTLCache` mantiene generaciones por prefijo; cada GET captura la generación antes de consultar servicio y solo escribe si sigue vigente. `invalidate_prefix` y `clear` avanzan la generación bajo el mismo lock. Agregada prueba concurrente determinista con eventos para intercalar GET antiguo y PATCH.
- **Filtros exactos:** eliminada la normalización de whitespace de las claves; `None`, vacío y valores con espacios se codifican de forma distinta, conforme a igualdad exacta en `get_all_suppliers`. Añadido test endpoint para espacios inicial/final.
- **Medición:** `measure_cache.py` ahora emite una muestra MISS por variante tras invalidación y calcula estadísticas HIT separadas. Expiración espera más que el TTL máximo. Se retiraron las cifras anteriores de `CACHING_REPORT.md` porque mezclaban MISS/HIT y la fase expiry no esperaba.
- **Validación:** backend `116 passed, 5 skipped`; backoffice Vitest `77 passed`, lint PASS, build PASS y typecheck PASS tras regenerar `.next/types`. Un mock de perfil que seguía usando la forma antigua se alineó a `{ user, profile }`.
- **Estado:** ambos conflictos resueltos, índice sin archivos unmerged y `git diff --cached --check` limpio. Merge y cambios listos en staging; aún no se ha hecho commit ni push.

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

## Integración PR #9: Recuperación y Cambio de Contraseña

- **Alcance aislado:** se descartaron las copias antiguas de incidentes,
  proveedores y autenticación incluidas en la rama, conservando las versiones
  ya verificadas de `main`.
- **Flujo completo:** se añadieron solicitud de recuperación, token JWT de uso
  único con expiración, restablecimiento, cambio autenticado y envío por Resend.
- **Privacidad:** la respuesta pública de recuperación es idéntica para cuentas
  existentes e inexistentes. El enlace sólo se devuelve si
  `AUTH_DEBUG_RESET_LINKS=true`; nunca se expone automáticamente por usar
  localhost.
- **Persistencia aislada:** los metadatos de tokens usan una tabla TinyDB
  dedicada y las pruebas la reemplazan por almacenamiento temporal.
- **Frontend:** nuevas rutas `/forgot-password`, `/reset-password` y
  `/account/change-password`, enlazadas desde login y perfil; cliente API
  corregido para respetar el proxy de Next.js y autorización Bearer.
- **Validación:** 84 pruebas backend verdes y 5 integraciones PostgreSQL
  omitidas; 67 pruebas frontend, typecheck y lint sin errores; build exitoso de
  19 rutas.
- **Dependencias:** `httpx` queda disponible en producción para Resend y
  `httpx2` se conserva en desarrollo para el `TestClient` de Starlette 1.6.
- **Alcance protegido:** no se modificaron ni fusionaron las PR #15 y #16.
- **Contexto histórico:** esta integración de PR #9 se documentó antes de los
  cambios posteriores de serialización y feedback de PR #15.

## Hito: Plan de Telemetría de Brasaland (rama `docs/telemetry-design-plan`)

- **Documento Canónico (`docs/telemetry/telemetry-plan.md`)**: Arquitectura integral de observabilidad y producto cubriendo las 19 secciones normativas, matriz de trazabilidad y gobernanza Zero-PII.
- **Contratos JSON Schema (`docs/telemetry/event-schemas.json`)**: Esquema canónico en Draft 2020-12 validado con 32 eventos (10 obligatorios y 22 oportunidades) bajo envelope unificado y allowlist estricta (`additionalProperties: false`).
- **Trazabilidad de Métricas**: Cobertura demostrable de alertas de stock crítico, ciclo de pedidos de ingredientes, ventas en COP/USD, alerta de cero ventas en horario operativo y visibilidad consolidada de compras/proveedores.
- **Validación Formal**: 100% de paridad semántica entre Markdown y JSON Schema, validado con `Draft202012Validator` en Python y suite de 32 payloads de prueba sin errores ni dependencias añadidas.

## Hito: Captura de Eventos de Telemetría (Backoffice Brasaland, rama `feat/telemetry-event-capture`)

- **Receptor FastAPI (`services/api/app/domains/telemetry/`)**: Endpoint `POST /telemetry/events` con modelos Pydantic V2 (`extra="forbid"`), envelope canónico SemVer 1.0.0, validación de lote (hasta 20 eventos), respuesta `{"received": N}`, logging Zero-PII y sin persistencia en base de datos ni archivos.
- **Configuración de Backend**: Variable de entorno `TELEMETRY_ENDPOINT` documentada en `services/api/.env.example`.
- **Servicio Frontend (`uis/backoffice/src/services/telemetry.ts`)**: `TelemetryService` singleton con `track()`, autocompletado de envelope con UUIDs y timestamp UTC, sesión diferida en `sessionStorage` (sin JWT), `userId` seudonimizado, buffer en memoria con disparador doble (20 eventos o 10s de espera), reintentos exponenciales con jitter (hasta 3 reintentos conservando `eventId`) y vaciado en cierre/ocultamiento (`navigator.sendBeacon` con fallback `keepalive: true`).
- **Integración Transversal y Core Web Vitals**: Componente `<WebVitals />` (`useReportWebVitals`), `<TelemetryBootstrap />` (navegación y captura de errores globales), medición monotónica de latencia en `InventoryApiClient` y sincronización de usuario en `AuthProvider`.
- **Instrumentación de Negocio en Vistas Reales**: Captura semántica en `InboundOrderForm` (`inbound_order_created`), `OutboundOrderForm` (`outbound_order_created`, `outbound_insufficient_stock_attempted`, `form_abandoned`), `ProductsTable` (`inventory_catalog_viewed`, `inventory_filter_applied` debounced 500ms) y `LoginPage` (`user_logged_in`, `user_login_failed`).
- **Validación Integral**: 97 pruebas backend en Pytest (13 nuevas en `test_telemetry_stub.py`), 78 pruebas frontend en Vitest (11 nuevas en `telemetry-service.test.ts`), 0 errores TypeScript, 0 errores ESLint y compilación de producción con Turbopack exitosa (19/19 páginas estáticas).
- **Contexto histórico:** esta integración de PR #9 se documentó antes de los
  cambios posteriores de serialización y feedback de PR #15.

## Feedback docente PR #18: cobertura de eventos obligatorios

- `OutboundOrderForm` ahora emite `stock_threshold_triggered` tras una salida aceptada cuando el saldo cruza el mínimo configurado; los valores de stock, déficit y severidad se derivan de la actualización optimista del formulario.
- Se añadió una prueba de regresión para el cruce de 25 a 19 con mínimo 20. Validación enfocada: `npm --prefix uis/backoffice run test -- src/test/inventory-orders-forms.test.tsx` pasó (8 pruebas).
- ESLint de los dos archivos modificados pasó. El typecheck completo sigue reportando 9 errores en otros archivos de la rama; ninguno corresponde a los archivos de este cambio.
- Siguen sin productor real los eventos obligatorios de compras, variación de precio, ventas/POS y alerta de sede sin ventas; no se fabricaron emisiones sin flujos de origen. El walkthrough registra ese alcance pendiente.
## Revisión de comentarios del profesor — PR #17 (telemetría)
- **Zero PII en propiedades diagnósticas:** `rejection_reason`, `field_name`, `error_rule`, `exception_class` y `error_code` quedaron restringidos por enums sincronizados entre el catálogo Markdown y el JSON Schema. Los valores desconocidos deben normalizarse o provocar descarte del evento; no se permite fallback a mensajes, stack traces ni cuerpos externos.
- **Métrica:** renombrada a `METRIC_AVERAGE_SPEND_PER_COVER` y propiedad `average_spend_per_cover`, con fórmula `total_sales_amount / total_covers` y aclaración de que no es ticket por transacción.
- **Clasificación:** catálogo confirmado en 32 eventos: 10 `mandatory` y 22 `opportunity`; `user_logged_in` es `opportunity`.
- **Autenticación:** guía corregida para emitir eventos en `login()` de `services/api/app/domains/auth/router.py`; fallos usan códigos normalizados y omiten credenciales y mensajes de excepción.
- **Validación:** metaschema Draft 2020-12 correcto, 32 IDs iguales entre Markdown y JSON, conjuntos de propiedades/requeridos coincidentes, y `git diff --check` limpio.

## Hito RAG y Base de Conocimiento — reinicio limpio

- **Base y aislamiento:** trabajo nuevo en `feature/rag-knowledge-base-restart`, creado desde
  `f18688e583aba6d912e4a887b17ec3baf2dd0806`. No se recuperaron archivos, commits ni
  stashes del RAG retirado y no se incorporaron otros hitos.
- **Fuentes oficiales:** contexto y cuatro manuales descargados nuevamente desde
  `4GeeksAcademy/ai-engineering-syllabus` en la revisión
  `b0489cb8eeba892b15aaae88b5341a326d546b9a`; hashes y URLs inmutables registrados en
  `docs/rag/sources.json`.
- **Corpus y pipeline:** 14 chunks semánticos (5 lealtad, 3 desperdicio, 3 alérgenos,
  3 proveedores), payload oficial, UUIDv5 deterministas, `setup`, `embed`, `retrieve`,
  `generate_answer` y `query` separados. La colección `brasaland_knowledge` usa COSINE,
  rechaza contratos incompatibles y elimina sólo chunks obsoletos del propietario RAG.
- **Integraciones:** Qdrant 1.16.3 persistente en Compose; SDK 1.16.2; endpoint autenticado
  `POST /knowledge/query`; pantalla protegida `/backoffice/knowledge` con sesión, proxy,
  carga, error, reintento y estilos claro/oscuro.
- **Proveedores:** el usuario aún no tiene confirmados el acceso, endpoints ni modelos de
  estudiante de 4Geeks. Los conectores carecen de defaults de URL/modelo/credenciales y
  sólo se activan tras una confirmación explícita del contrato. No se usaron servicios de pago.
- **Evaluación preparada:** 16 preguntas dentro del corpus y 2 fuera de alcance. Un acierto
  exige que un mismo chunk del top 3 pertenezca al manual correcto y contenga toda la evidencia.
  Recall@3, umbral y fidelidad reales quedan pendientes; no se atribuyen métricas a mocks.
- **Verificación sin modelos reales:** 185 pruebas Python aprobadas y 5 integraciones de
  inventario PostgreSQL omitidas sin `TEST_DATABASE_URL`; 100 pruebas del backoffice aprobadas.
  Qdrant saludable, setup repetido con vectores simulados conservó 14 puntos, imagen Docker
  compilada y recorrido navegador con proveedor simulado verificó login, respuesta, error y
  reintento en escritorio y móvil.
- **Baseline preservado:** typecheck conserva exactamente tres errores preexistentes en
  auth/telemetría; lint global conserva dos errores preexistentes en telemetría; build conserva
  el fallo de descarga de Google Fonts. El lint dirigido de archivos RAG pasó.
- **Estado (16-oct-2026):** a petición del usuario, se cierra localmente el alcance
  simulado. Las validaciones offline y mock citadas arriba ya estaban registradas y
  no se repitieron en esta sesión. Recall@3, fidelidad, calibración y recorrido con
  modelos reales siguen diferidos; no se presentan mocks como métricas reales. Sin
  commit, push ni PR.

## Feedback docente PR #29: Integración real del modelo Gemini y validación E2E del RAG (19-oct-2026)

- **Feedback atendido:** *"Carlos, todavía quedan pendientes partes clave del RAG, como la integración real del modelo y la validación E2E."*
- **Proveedor y contrato real (Google Gemini):** configurado `RAG_HTTP_CONTRACT=embeddings-chat-v1` contra los endpoints compatibles con OpenAI de Gemini (`gemini-embedding-001` a `768` dimensiones en formato `float` y `gemini-3.5-flash-lite` para generación sin herramientas externas).
- **Ajustes en conectores y evaluador:**
  - `data/process/config.py`: soporte de clave única (`RAG_EMBEDDING_API_KEY`, `RAG_API_KEY` o `GEMINI_API_KEY`) reutilizada automáticamente para embeddings y generación.
  - `data/process/embeddings.py`: tolerancia a la omisión del campo opcional `"index"` en respuestas unitarias de Gemini (`item.get("index", 0) != 0`).
  - `data/eval/run.py`: separación entre `Recall@3` (`all_retrieved[:3]`) y `generation_context` (`k=5`, alineado con `data.pipelines.rag.query`), más soporte `--delay` para cuotas de API.
  - `docker-compose.yml`: retiro de `QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY:-}` vacío que causaba `401 Unauthorized` en Qdrant v1.16.3 cuando no se definía clave.
- **Indexación e idempotencia reales:** `data.process.smoke` aprobado (`768` dims) y doble corrida de `data.process.rag` sobre Qdrant v1.16.3 persistente (`indexed: 14, removed: 0`, vector `embedding_c874deab2e0c764cb87fb252`).
- **Calibración y Evaluación (`data/eval/rag-evaluation-01.json`):** `RAG_MIN_SCORE=0.60` calibrado experimentalmente (consultas en corpus `0.6170`–`0.7751`; fuera de corpus $\le 0.5637$). **Recall@3 = 16/16 (100.0%)**, superando el objetivo `>= 13/16`. Las 19 generaciones reales (16 en corpus, 2 fuera de corpus y 1 prueba de inyección hostil) fueron auditadas y aprobadas manualmente en `docs/rag/rag-evaluation-report.md`.
- **Validación E2E multicapa:** verificada con Qdrant (`:6333`), FastAPI (`:8000`) y Next.js Backoffice (`:3001`) levantados simultáneamente, ejecutando registro, login JWT y consultas reales a través del proxy `/api/knowledge/query` para casos de lealtad, alérgenos/Costilla BBQ y fuera de alcance (ventas en Miami).
- **Pruebas automatizadas:** `191 passed, 5 skipped` en Python (`49` en `tests/pipelines/test_rag.py` + `142` en `services/api/tests`) y `107 passed` en Vitest (`uis/backoffice`).

## Hito: Agente de Soporte con LangGraph — Parte 1: Migración y Flujo del Agente (rama `feature/langgraph-agent-base`)

- **Base Git verificada:** creada desde `main` actualizado (`1a34b24707f6f7cc1ebece228ab59a12d0bb4f4a`, tras el merge de la PR #29).
- **Dependencia:** añadido `langgraph` en `services/api` mediante `uv add --project services/api langgraph` (`uv.lock` verificado).
- **Estado mínimo y explícito (`services/api/app/domains/agent/state.py`):** `AgentState` tipado con `run_id`, `question`, `retrieved_context`, `answer`, `route` y `error_code`, más validador en tiempo de ejecución `validate_agent_state()` que rechaza historiales conversacionales, tokens/claves y clientes HTTP/BD.
- **Grafo compilado y nodos independientes (`services/api/app/domains/agent/graph.py`):**
  - `receive_question`: normaliza y valida la pregunta (`valid` vs `empty_question`).
  - `reject_invalid_question`: ruta condicional que termina en `END` sin consultar Qdrant ni el LLM cuando la pregunta está vacía o fuera de rango.
  - `retrieve_context`: importa y llama directamente a `retrieve()` de `data.pipelines.rag`.
  - `generate_grounded_answer`: importa y llama a `generate_answer(question, context)` con el `retrieved_context` del estado cuando hay evidencia ($\ge 1$ chunk).
  - `abstain_without_evidence`: ruta condicional explícita cuando `retrieved_context == []`, garantizando abstención honesta sin inventar datos.
  - Compilación explícita (`COMPILED_AGENT_GRAPH`) con `InMemorySaver` por `thread_id` aislado; `rag.query()` nunca se invoca dentro del grafo.
- **Checkpoints y Traces consultables (`services/api/app/domains/agent/traces.py`):**
  - Funciones de inspección `get_run_state(thread_id)` y `get_run_checkpoints(thread_id)` sobre `get_state` / `get_state_history`.
  - Persistencia automática por corrida en JSON local (`services/api/data/agent_traces/<run_id>.json`, ignorado en Git) con `nodes_order`, `steps` (duración y fuentes recuperadas), `checkpoints`, `retrieved_context`, `answer` y errores sanitizados.
  - Export de corrida real contra Qdrant + Google Gemini versionado en `data/eval/langgraph-agent-trace-01.json`.
- **Endpoint autenticado (`services/api/app/domains/agent/router.py`):** `POST /agent/query` protegido con `Depends(get_current_user)`, conviviendo con `POST /knowledge/query` y sanitizando errores (422/502/503/500) sin filtrar stack traces ni secretos.
- **Evaluaciones y pruebas:**
  - `tests/pipelines/test_agent_evals.py` + `tests/pipelines/fixtures/agent_traces.json`: 3 evals sobre traces guardados y corrida real (flujo nominal y orden de nodos, rutas condicionales alternativas sin evidencia/pregunta vacía, y anclaje de políticas de Brasaland: Nivel Oro `50+ puntos` / `15%` y Costilla BBQ / contaminación cruzada) + pruebas estructurales, aislamiento de checkpoints y sanitización.
  - `tests/pipelines/`: `67 passed` (`49` RAG + `18` LangGraph).
  - `services/api/tests`: `156 passed, 5 skipped` (`14` nuevas en `test_agent_api.py`).
