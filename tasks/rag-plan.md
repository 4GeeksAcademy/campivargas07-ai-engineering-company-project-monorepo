# Plan de implementación: Hito 7 — RAG y Base de Conocimiento de Brasaland

**Estado:** planificación solamente; no se ha implementado ni instalado nada.

**Alcance:** ingestión de cuatro manuales oficiales en Qdrant, consulta FastAPI autenticada y vista protegida en Backoffice.
**No incluye:** LangChain, LlamaIndex, LangGraph, agentes, nuevas políticas de negocio ni cambios a PRs.

## 1. Estado verificado y bases de trabajo

El checkout está limpio sobre `main` (`810a873`, `origin/main`). El historial y GitHub no coinciden con la premisa proporcionada sobre los números de PR:

- La PR #27 real está **merged** a `main` (2026-07-22); su head fue `patch-1` y sólo corrigió un typo del README. No es la PR de evaluación de regresión.
- La PR #26 está **closed, no merged**; su head fue `Desarrollando-scripts-para-automatizar-tareass`.
- `origin/feature/regression-model-eval` sí existe y contiene el commit exclusivo `d2c65e7` más cambios de su historial, pero GitHub la asocia con la PR #73, **closed, no merged**, dirigida a `main`.

**Decisión de rama:** proponer `feature/rag-knowledge-base` desde el `origin/main` actualizado. No apilar Hito 7 sobre una PR cerrada sin merge ni incorporar silenciosamente regresión de ventas, que no es dependencia funcional del RAG. La futura PR será hacia `main`, titulada exactamente **`feat: rag knowledge base`**. Si el equipo confirma que la rama de regresión debe formar parte del entregable, resolver primero el estado/base de la PR #73; no se cambia PR ni rama en esta sesión.

La memoria describe `services/api` como FastAPI activo; `services/backend` pertenece a un backend anterior y queda fuera de alcance. `tasks/plan.md` y `tasks/todo.md` describen el dominio de inventario ya completado. Se conservan como historial: se añaden estos archivos específicos y no se reescriben esos planes.

## 2. Fuentes oficiales y conservación

`CONTEXT.md` es el brief general en inglés; `company-choice.md` registra la selección de empresa; `docs/CONTEXT-brasaland.es.md` es el contrato histórico del analizador de incidentes. Ninguno sustituye al contexto del Hito 7, y ninguno debe modificarse ni sobrescribirse.

Conservar una copia del contexto oficial RAG en `docs/rag/CONTEXT-brasaland.es.md`, junto a `docs/rag/rag-design.md`. Registrar su URL de origen y fijar la revisión consultada `bc4c7c86e09cc336317c7acba5a41a108925f4bb` del syllabus. Conservar el texto oficial, haciendo explícita la procedencia y la revisión en la documentación de RAG.

Copiar íntegramente, sin traducir ni normalizar cifras, los cuatro archivos oficiales a `docs/company-knowledge-base/`. Para reproducibilidad, fijar como revisión de corpus consultada `48e21bb4c45a4101abb09cff8e6e0ad941c87847` y referenciar los blobs de esa revisión:

| `source_document` | Archivo local | Origen fijado |
|---|---|---|
| `loyalty-program` | `docs/company-knowledge-base/brasaland-loyalty-program.es.md` | [`brasaland-loyalty-program.es.md`](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-loyalty-program.es.md) |
| `waste-protocol` | `docs/company-knowledge-base/brasaland-waste-protocol.es.md` | [`brasaland-waste-protocol.es.md`](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-waste-protocol.es.md) |
| `menu-allergens` | `docs/company-knowledge-base/brasaland-menu-allergens.es.md` | [`brasaland-menu-allergens.es.md`](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-menu-allergens.es.md) |
| `supplier-ordering` | `docs/company-knowledge-base/brasaland-supplier-ordering.es.md` | [`brasaland-supplier-ordering.es.md`](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-supplier-ordering.es.md) |

La aceptación de esta fase compara cada copia byte a byte con su blob fijado, verifica la revisión anotada y confirma que los contextos anteriores permanecen intactos.

## 3. Arquitectura y flujo

```mermaid
flowchart LR
  Docs[Manuales oficiales fijados] --> Setup[data/process/setup.py]
  Setup --> Chunk[Chunk semántico]
  Chunk --> Embed[data/process/embeddings.py]
  Embed --> Qdrant[(Qdrant brasaland_knowledge)]
  User[Gerente autenticado] --> UI[Backoffice /backoffice/knowledge]
  UI -->|POST /api/knowledge/query| Proxy[Rewrite Next.js /api]
  Proxy --> Router[FastAPI POST /knowledge/query]
  Router --> Query[data/pipelines/query.py]
  Query --> Retrieve[retrieve: embed + query_points + min_score]
  Retrieve --> Qdrant
  Retrieve --> Generate[generate_answer: prompt + generación]
  Generate --> Router
  Router -->|{answer}| UI
```

1. `setup()` carga los cuatro Markdown completos, segmenta por unidades semánticas, obtiene embeddings reales y sincroniza puntos en `brasaland_knowledge`.
2. El cliente HTTP del backoffice añade el Bearer token ya gestionado por `authApi`; el rewrite existente transforma `/api/knowledge/query` en la ruta backend `/knowledge/query`.
3. FastAPI valida la petición y el usuario actual, llama a `query(question)` y devuelve exclusivamente `{"answer":"..."}`. Ni IDs, scores, payloads ni chunks de Qdrant pasan al contrato HTTP.
4. `query()` compone `retrieve()` y `generate_answer()`. Ambas funciones quedan en `data/pipelines/`, con interfaces independientes del router para reutilizarlas más adelante desde LangGraph, sin introducirlo en este hito.

### Responsabilidades y archivos Python propuestos

| Archivo | Responsabilidad / contrato |
|---|---|
| `data/process/loader.py` | Leer exclusivamente los cuatro paths permitidos y asociar cada uno a su slug. No leer contexto de incidentes como corpus RAG. |
| `data/process/chunking.py` | Convertir Markdown en chunks autocontenidos con heading de origen, sin separar regla de condición/excepción. |
| `data/process/embeddings.py` | `embed(text) -> list[float]`; cliente real del proveedor de embeddings, usado por ingestión y preguntas. |
| `data/process/qdrant_store.py` | Cliente/configuración de Qdrant, creación y validación de colección, sincronización y borrado de IDs obsoletos. |
| `data/process/setup.py` | `setup()`: lectura, chunking, embeddings e indexación idempotente. Orquesta módulos anteriores. |
| `data/pipelines/retrieval.py` | `retrieve(query, *, k=5, min_score) -> list[dict]`; embed de consulta, consulta Qdrant, filtrado y orden por score. |
| `data/pipelines/generation.py` | `generate_answer(question, context) -> str`; prompt en español, cliente de generación, cita de fuentes e insuficiencia. |
| `data/pipelines/query.py` | `query(question) -> str`; convierte resultados recuperados en contexto y llama al generador. |
| `data/__init__.py`, `data/process/__init__.py`, `data/pipelines/__init__.py` | Hacer explícitos los paquetes compartidos si son necesarios para imports reproducibles. |

`setup` puede invocarse manualmente como tarea de preparación; no debe reindexar en cada petición ni bloquear el arranque de FastAPI. La API consume el paquete raíz `data` por import, no copia lógica a `services/api`. Para que funcione tanto localmente como en el Compose actual, añadir el root del monorepo a `PYTHONPATH`/path de ejecución y montar el código de `data` y los manuales de solo lectura donde el contenedor pueda importarlos/leerlos. Documentar el mismo requisito en el comando de pruebas local. No alterar el `SUPPLIERS_DB_PATH` actual ni superponer `services/data` con el `data/` raíz.

## 4. Chunking y contrato de Qdrant

Nombre de colección exacto: `brasaland_knowledge`. Cada punto incluye al menos:

```json
{
  "company": "brasaland",
  "source_document": "loyalty-program | waste-protocol | menu-allergens | supplier-ordering",
  "section": "título/subtítulo del Markdown de origen",
  "language": "es",
  "chunk_index": 0,
  "text": "texto original autocontenido"
}
```

`section` toma el encabezado literal más cercano del documento; si una unidad no tiene subtítulo propio, usa el título literal del manual. No se inventan encabezados con significado de política. Se permite metadata adicional no obligatoria, como `source_sha256` y revisión del corpus, para evitar re-embeddings innecesarios y hacer trazable una actualización.

| Manual | Unidades semánticas iniciales a comprobar al implementar |
|---|---|
| Lealtad | (1) acumulación, vigencia y condición de cuenta activa, manteniendo juntos COP/USD y los 12 meses; (2) umbrales y beneficios de Bronce/Plata/Oro; (3) redención, mínimo, incrementos, equivalencia monetaria y no acumulación de promociones; (4) canales, transferencia única y preguntas frecuentes, incluida validez en ambos países/tipo de cambio. |
| Desperdicio | (1) categorías, registro por turno y nota obligatoria para proteína; (2) causas aceptadas sin nota y excepción temporal de entrenamiento, junto a sus condiciones; (3) alerta por merma semanal y sus límites; (4) escalamiento a Felipe y metas mensuales, incluyendo el período consecutivo del plan de mejora. |
| Alérgenos | (1) declaraciones de Lomo, Costillas y Pollo, preservando por plato “contiene”, “puede contener trazas” y declaraciones negativas; (2) Ensalada, Arepa y Salsa con sus alérgenos; (3) protocolo de aviso y separación de utensilios/superficie; (4) advertencia literal de contaminación cruzada y ausencia de versión certificada sin gluten de Costilla BBQ. |
| Proveedores | (1) responsable, día y hora límite local; (2) las cuatro categorías con frecuencia y plazo de entrega juntos; (3) mínimo de inventario, condición para pedido de emergencia y recargo; (4) aprobación de Lucía, umbral y equivalencia COP/USD juntos. |

Cada documento debe producir **al menos 3 chunks autocontenidos**; las unidades de arriba dan una meta inicial de 3–4, no un límite rígido. Priorizar integridad semántica sobre un corte fijo: orientar inicialmente a 250–450 tokens/chunk cuando el contenido lo permita. Estos manuales son cortos, por lo que un chunk menor sigue siendo correcto si representa una unidad completa; nunca rellenar ni mezclar políticas para alcanzar el tamaño. No partir enumeraciones, cifras, monedas, condiciones, excepciones o advertencias de alérgenos. Repetir el título/heading de origen resuelve referencias elípticas. Solapamiento predeterminado: **0 tokens** para evitar duplicar reglas en estos textos breves; permitir alrededor de 30–50 tokens sólo si una unidad extensa necesita dividirse y el antecedente de una condición quedaría huérfano. Registrar el resultado real y el recuento por documento en la evaluación.

### IDs, dimensión e idempotencia

- Generar IDs UUID deterministas con `uuid.uuid5` y un namespace fijo del proyecto, usando `(company, source_document, chunk_index)` como clave estable. El ID cumple el formato admitido por Qdrant y un cambio de texto en un índice sustituye el punto anterior mediante upsert.
- Tras cargar el conjunto deseado de un documento, comparar sus IDs con los IDs actuales filtrados por ese `source_document` y borrar los sobrantes. Así, reducir/cambiar la cantidad de chunks no deja puntos huérfanos. Ejecutar `setup()` dos veces con fuentes/configuración iguales debe dejar el mismo conjunto de IDs y textos; una revisión modificada reemplaza texto/vector y elimina IDs obsoletos.
- Usar `Distance.COSINE`. Obtener la dimensión de un embedding real devuelto por el modelo elegido al inicializar una colección nueva; validar que todos los embeddings de documentos y consulta tengan esa longitud. Si la colección existente no coincide, fallar con error explícito y **no** recrearla ni borrar datos automáticamente. Cambiar de modelo/dimensión requiere migración/reindexación deliberada.
- Consultar la API del cliente actual antes de codificar: la documentación vigente muestra `create_collection(... VectorParams(size=..., distance=...))`, `upsert(... PointStruct(...), wait=True)` y `query_points(...).points`; no basarse en ejemplos antiguos de `search`. Versiones comprobadas al redactar: `qdrant-client 1.19.1` publicado en PyPI y servidor `qdrant/qdrant:v1.19.2`. Fijar versiones compatibles en `pyproject.toml` y Compose y contrastar el lock/API durante implementación.

## 5. Configuración, proveedor y despliegue local

El repo ya incluye `httpx` como dependencia de producción y no contiene variables ni cliente/modelos de embeddings o generación. Añadir `qdrant-client` como dependencia nueva necesaria; reutilizar `httpx` para los proveedores si el API estudiantil confirmado lo permite. No añadir SDK de OpenAI, LangChain, LlamaIndex ni dependencia agente sin una necesidad demostrada.

Mantener configuración separada para vector store, embeddings y generación; agregar nombres/explicación sin valores secretos a `services/api/.env.example` y pasar por entorno en `docker-compose.yml`:

| Grupo | Variables a definir | Confirmación requerida |
|---|---|---|
| Qdrant | `QDRANT_URL` (Compose: `http://qdrant:6333`), colección constante `brasaland_knowledge`; `QDRANT_API_KEY` sólo si el proveedor/entorno la exige. | Host local, exposición de puerto; dimensiones no se configuran a mano sino que se miden/validan contra el embedding. |
| Embeddings | `EMBEDDING_API_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_API_KEY`; timeout configurable. | Proveedor/modelo estudiantil exacto, URL/ruta y protocolo/payload, autenticación, límite de entrada, dimensión de salida, rate limit y permanencia del modelo. |
| Generación | `GENERATION_API_BASE_URL`, `GENERATION_MODEL`, `GENERATION_API_KEY`, `GENERATION_TEMPERATURE`, `GENERATION_MAX_TOKENS`; timeout configurable. | Proveedor/modelo estudiantil exacto, URL/ruta/protocolo, autenticación, contexto máximo, controles de salida y límites de uso. |
| Recuperación | `KNOWLEDGE_MIN_SCORE` tras calibración; `k=5` es default contractual de `retrieve`. | Score threshold observado para el modelo real; no representarlo como porcentaje ni probabilidad. |

Priorizar los modelos habilitados para estudiantes de 4Geeks, pero no inventar sus identificadores, URLs, dimensiones, payloads ni claves. Antes de implementación, obtener acceso/documentación sin compartir secretos en el repo ni en la respuesta. Si los endpoints no son compatibles con una API común, implementar adaptadores HTTP pequeños separados para embedding y generación en vez de fingir compatibilidad. El mismo `EMBEDDING_MODEL` y preprocesamiento deben usarse para manuales y preguntas. No derivar la dimensión de ejemplos, documentación o modelo de generación.

En `docker-compose.yml`, añadir servicio Qdrant fijado a versión, con volumen nombrado `qdrant_storage:/qdrant/storage`, restart policy y red `brasaland-dev`. La API recibe sólo el host interno. Como el Qdrant local no tiene autenticación por defecto, no publicar su puerto a todas las interfaces: si se necesita acceso desde host, ligarlo a loopback. Montar `data/` y `docs/company-knowledge-base/` raíz en paths propios, de solo lectura para FastAPI; conservar separados `./services:/app` y `services/api/data` (TinyDB). Ajustar la preparación de servicio/Compose para que `data.pipelines` sea importable en el contenedor; documentar `PYTHONPATH` para ejecución fuera de Compose. Añadir health/dependency readiness de Qdrant sin asumir herramientas que no existan en su imagen. La configuración no debe cambiar las bases PostgreSQL/TinyDB existentes.

## 6. Recuperación, generación, fidelidad y endpoint

### Pipeline

- `embed(text) -> list[float]` solicita un embedding real, valida lista numérica finita y dimensiona con el modelo; misma función/modelo en `setup` y `retrieve`.
- `retrieve(query, *, k=5, min_score) -> list[dict]` obtiene el vector de consulta y llama a `query_points` con `limit=k`, payload requerido y threshold de score. Devuelve resultados válidos ordenados, con cero a `k` elementos; no rellena con resultados por debajo del umbral ni asume que habrá cinco.
- `query(question) -> str` convierte sólo los chunks aceptados en contexto, incluyendo nombre legible del documento/section como evidencia. Si no hay resultados, pasa contexto vacío a `generate_answer`.
- `generate_answer(question, context) -> str` usa generación real y siempre tiene conducta definida incluso con `context == ""`: solicita respuesta en español, clara como vendedor entrenado; si no hay evidencia suficiente, debe decirlo expresamente y no completar desde memoria del modelo. Pide citar el documento por nombre dentro de la respuesta. No devuelve chunks como sustituto de respuesta.

El prompt separa instrucciones confiables y contexto citado como **datos no confiables**; ordena ignorar instrucciones embebidas en documentos y no permitir que alteren las reglas. Limita hechos al contexto recuperado, conserva montos/monedas y redacción de advertencias oficiales. Para alérgenos debe preservar “puede contener trazas”, no garantizar ausencia de riesgo y comunicar que Costilla BBQ no tiene versión sin gluten certificada. Ninguna conversión automática COP/USD.

El prompt por sí solo no es una garantía de fidelidad. Además de evaluación humana contra evidencia, implementar una comprobación determinista de afirmaciones cuantitativas en la respuesta (cifras, porcentaje, unidades, COP/USD) contra chunks entregados al modelo; si encuentra un dato sin respaldo, sustituir por una respuesta segura de información insuficiente, no devolver la cifra. Las condiciones y advertencias cualitativas se revisan en evaluación de claims; conservar hallazgos como evidencia, sin declarar verificación total sólo por una cita.

### FastAPI y contrato observable

Añadir `services/api/app/domains/knowledge/{__init__.py,schemas.py,router.py}` y registrar el router desde `services/api/app/main.py`.

```http
POST /knowledge/query
Authorization: Bearer <sesión existente>
Content-Type: application/json

{"question":"¿Cuántos puntos necesito para el nivel Oro?"}
```

Respuesta exitosa: `{"answer":"..."}`. Un schema Pydantic valida pregunta no vacía y respuesta como string. El router usa `Depends(get_current_user)` —la misma autenticación OAuth2 Bearer existente— y delega a `query()`; prueba que no filtre resultados crudos de Qdrant. Definir errores HTTP sin stack trace, URL ni secreto del proveedor. El frontend usa el rewrite ya configurado en `uis/backoffice/next.config.ts`: llamar `/api/knowledge/query`, que llega a FastAPI como `/knowledge/query`.

### Backoffice

Añadir ruta protegida `uis/backoffice/src/app/backoffice/knowledge/page.tsx`, componente cliente `uis/backoffice/src/components/knowledge/KnowledgeAssistant.tsx` y CSS module, y `uis/backoffice/src/lib/knowledge-api.ts`. Reutilizar `AuthGuard`, `authApi.getToken()` y patrón de request/error de `incidents-api.ts`; incluir la entrada “Base de conocimiento” en `BackofficeHeader` (un nuevo valor de `activeView`). Interfaz en español con formulario de pregunta, deshabilitado mientras carga, estado de carga accesible, respuesta como texto normal (incluida cita), error `role="alert"`, reintento mediante nueva pregunta y sin mostrar scores/chunks crudos.

El backoffice actual tiene tokens globales `--bg`, `--fg`, `--muted`, `--card`, `--border` y CSS Modules, pero `globals.css` no define hoy una paleta clara; la única regla de preferencia localizada está en un CSS de plantilla no usado por esta ruta. El hito debe añadir un override mínimo de `prefers-color-scheme: light` a los tokens/superficies compartidos, manteniendo el modo oscuro actual, y usar esos tokens en la nueva vista. No crear un sistema de temas/dependencia aparte ni dejar controles de bajo contraste.

## 7. Plan de trabajo y archivos

| ID / fase | Archivos objetivo | Dependencias | Aceptación y verificación |
|---|---|---|---|
| R0 — Base | Ningún archivo funcional; crear rama al iniciar implementación. | Confirmación de decisiones abiertas abajo. | Rama nueva desde `origin/main`; registrar SHA de base; sin incluir commits exclusivos de la PR #73. |
| R1 — Fuentes fijadas | Añadir `docs/rag/CONTEXT-brasaland.es.md`; añadir cuatro `docs/company-knowledge-base/*.md`. | R0; blobs revisados en secciones 2. | Cuatro archivos completos, comparación byte a byte contra SHA fijado; contexto incidente y contextos anteriores preservados. |
| R2 — Entorno | `services/api/pyproject.toml`, `services/api/uv.lock`, `services/api/.env.example`, `docker-compose.yml`, `services/Dockerfile` sólo si el layout/contexto de build lo exige. | R0; modelo/proveedor para ejecutar llamadas reales. | Dependencia cliente fijada/lock actualizado; Qdrant persistente; env separado sin secretos; API ve paquetes/docs raíz y preserva TinyDB. `uv sync --locked` sólo durante implementación autorizada. |
| R3 — Embedding y chunking | Añadir `data/__init__.py`, `data/process/__init__.py`, `loader.py`, `chunking.py`, `embeddings.py`. | R1, R2 y endpoint estudiantil confirmado. | Corpus reconocido exactamente; ≥3 chunks por documento, unidades autocontenidas; dimensiones/valores válidos; `embed` compartido entre setup y consulta. Pruebas unitarias de chunking y adapter mockeado. |
| R4 — Qdrant y setup | Añadir `data/process/qdrant_store.py`, `setup.py`. | R2–R3 y dimensión del modelo real. | Colección exacta, cosine, UUIDv5 estable; upsert idempotente; los chunks antiguos se borran por fuente; mismatch de dimensión falla sin recrear colección. Qdrant en memoria y prueba de segunda ejecución. |
| R5 — Pipelines | Añadir `data/pipelines/__init__.py`, `retrieval.py`, `generation.py`, `query.py`. | R3–R4; modelo de generación confirmado. | Umbral filtrado, resultados 0..k, contexto vacío explícito, cita y salida textual; defensa de contexto no confiable y validador cuantitativo. Pruebas con Qdrant in-memory y modelos HTTP simulados. |
| R6 — API | Añadir `services/api/app/domains/knowledge/{__init__.py,schemas.py,router.py}`; cambiar `services/api/app/main.py`; añadir `services/api/tests/test_knowledge_api.py`. | R5. | `POST /knowledge/query` protegido, request/response exactas, router llama `query`, ningún resultado crudo; prueba auth, contrato, delegación, salida e error controlado. |
| R7 — UI | Añadir ruta/componente/client/CSS module de Knowledge; cambiar `uis/backoffice/src/components/backoffice-header.tsx`, `uis/backoffice/src/app/globals.css`; añadir tests Vitest en el patrón existente. | R6 y rewrite existente. | Flujo pregunta/respuesta, carga/error, Bearer y AuthGuard; ruta `/api/knowledge/query`; legible con preferencia clara/oscura y responsive; pruebas Vitest, typecheck, lint y build. |
| R8 — Evaluación y entrega | Añadir `data/eval/test-queries.json`, `data/eval/run_evaluation.py`, `docs/rag/rag-design.md`, `docs/rag/rag-evaluation-report.md`; al finalizar la implementación actualizar `tasks/walkthrough.md` y `memory-bank/progress.md`. | R1–R7 y acceso a modelos reales. | Recall@3 real ≥80% en consultas dentro del corpus; evaluación de fidelidad con evidencias/chunks; informe registra modelos/revisiones/parámetros, resultado, riesgos y comandos; walkthrough y memoria actualizados antes de cerrar hito. |

No se cambia `tasks/plan.md` ni `tasks/todo.md`: el tracking de este trabajo vive en `tasks/rag-plan.md` y `tasks/rag-todo.md`. Tampoco se altera `CONTEXT.md`, `company-choice.md`, `docs/CONTEXT-brasaland.es.md`, `infra/` ni `mcps/`.

## 8. Matriz de requisitos de academia

| Requisito / evidencia | Tareas que lo satisfacen |
|---|---|
| Contexto del Hito 7 preservado con procedencia/revisión; cuatro fuentes completas y contexts anteriores conservados | R1, R8 |
| Slugs/colección/payload exactos, compañía e idioma | R3, R4, R8 |
| ≥3 chunks/documento y chunking semántico con excepciones juntas | R3 |
| Embedding real compartido y dimensión coincidente | R2, R3, R4 |
| setup idempotente y no conserva chunks obsoletos | R4 |
| Recuperación Qdrant vigente, `k=5`, threshold, 0..k resultados | R4, R5 |
| Generación grounded en español, insuficiencia, cita, contexto vacío y resistencia a instrucciones del corpus | R5 |
| COP/USD sin conversión; precisión de cifras; lenguaje de alérgenos no absoluto | R1, R3, R5, R8 |
| Endpoint POST, contrato `{question}` → `{answer}`, autenticado y sin exponer Qdrant | R6 |
| Backoffice protegido con loading/error y modos claro/oscuro | R7 |
| Tests retrieve/query/setup/dimensiones y contrato | R3–R7 |
| `data/eval/test-queries.json`, ≥8 consultas/fuentes, Recall@3 ≥80% real y fidelidad evaluada | R8 |
| Diseño, reporte, walkthrough, memoria y futura PR `feat: rag knowledge base` | R0, R8 |

## 9. Pruebas y evaluación

### Pruebas automatizadas aisladas

- `data/process` — los cuatro ficheros completos mapean a los slugs permitidos; cada uno produce ≥3 chunks; heading y texto originales; condiciones/excepciones permanecen juntas; importes y advertencias no se alteran. Embedding simulado valida una lista numérica y dimensiones inconsistentes.
- `setup` — usar `QdrantClient(":memory:")` con dimensión pequeña y embeddings stub; dos ejecuciones producen mismos IDs/payloads; cambiar un documento actualiza los puntos y elimina índices sobrantes; colección preexistente de dimensión diferente da error sin borrado.
- `retrieve` — usar colección en memoria o mocks: descarta resultados menores a `min_score`; respeta `k`; retorna menos de `k` sin completar artificialmente; ningún resultado aceptado retorna `[]`; scores y texto conservan orden y payload.
- `query`/generación simulada — invoca `retrieve` y `generate_answer`, pasa el contexto correcto (también `""`), retorna exactamente la salida textual del modelo, no transforma texto de importe; salida sin soporte numérico se reemplaza por fallback seguro. Caso de instrucción adversarial en el texto del documento se trata como datos.
- FastAPI — no autenticado recibe 401; autenticado recibe `{answer}`; monkeypatch de `query()` prueba que el router lo llama y sólo serializa el string. Añadir estas pruebas a `services/api/tests/` y conservar el aislamiento TinyDB/SQLite de `conftest.py`.
- UI — testear envío y respuesta, estado `role=status`, bloqueo durante la llamada, error `role=alert`, Bearer token, escape/render de texto y contrato exacto. Typecheck, ESLint y build sobre Backoffice.

Los mocks verifican contrato/control de flujo, no calidad de embeddings ni Recall. No contabilizarlos como evidencia del KPI de academia.

### Corpus de evaluación real

`data/eval/test-queries.json` tendrá inicialmente 16 preguntas in-domain, al menos cuatro por manual y campos para `id`, `question`, `expected_source_document` y `expected_section` (o varios esperados cuando una pregunta requiere evidencia de dos chunks). Añadir dos preguntas fuera del corpus con `expected_source_document: null`; reportarlas aparte y no incluirlas en el denominador de Recall@3.

Cobertura sugerida, sin redactar respuestas/políticas nuevas:

- Lealtad: COP frente a USD al acumular; vigencia/condición de cuenta; beneficios/umbral Oro; mínimo, incremento, equivalencia y promoción al redimir.
- Desperdicio: proteína >2 kg por turno y nota; causas aceptadas/entrenamiento; merma semanal >3%; escalamiento de proteína premium y metas 4%/6% con sus períodos.
- Alérgenos: declaración de Costillas y trazas de maní; pollo y sus declaraciones; ensalada/arepa/salsa; preparación ante alergia, contaminación cruzada y advertencia de Costilla sin gluten.
- Proveedores: día/hora local; frecuencia y plazo por categoría; 3 días de stock y condición/recargo de emergencia; aprobación >500 USD/equivalente COP.
- Fuera de corpus: horario exacto de una sede y una pregunta sobre ventas/stock actuales. Esperado: información insuficiente, nunca completar usando memoria.

`run_evaluation.py` llama modelos y Qdrant reales, usa los chunks recuperados y registra una ejecución sin secretos. **Recall@3** = preguntas in-domain cuyo chunk/sección esperado aparece entre los tres primeros resultados / consultas in-domain; el criterio es ≥80%. Los thresholds pueden reducir candidatos antes del top-3 y una omisión cuenta como miss.

Calibrar `KNOWLEDGE_MIN_SCORE` con distribución de score real de positivos y preguntas fuera de corpus, inspeccionando falsos positivos/negativos; elegir un punto operativo que mantenga Recall@3≥80% y limite contexto irrelevante. Registrar los scores observados y la decisión. El score de similitud no es probabilidad de que la respuesta sea correcta ni porcentaje de confianza.

La evaluación de fidelidad guarda para cada respuesta la pregunta, fuente/chunks recuperados, respuesta y decisión de revisión; comprobar trazabilidad de afirmaciones, citas, números, montos/moneda exactos, condiciones/excepciones, insuficiencia fuera del corpus y alertas de alérgenos. Cualquier cifra no presente en los chunks es fallo; revisar manualmente las advertencias de alto riesgo de alérgenos y condiciones. Reportar separado de Recall, contar casos fallidos y repetir tras cambios de chunking/modelo/prompt. Una respuesta fluida o una cita no prueban por sí solas fidelidad.

## 10. Contenido previsto de `docs/rag/rag-design.md`

1. Objetivo, usuarios y límite de respuestas a los cuatro manuales; diferencia frente a contexto local de incidentes.
2. Procedencia, commit fijado y política para actualizar/copiar fuentes oficiales.
3. Diagrama y módulos: ingestión, embeddings, Qdrant, retrieve/generate/query, FastAPI y UI.
4. Contrato de colección, payload, IDs UUIDv5, dimensión, actualización y limpieza de chunks obsoletos.
5. Parámetros confirmados y pendientes, variables de entorno, proveedor/modelos seleccionados y cómo guardar secretos fuera del repositorio.
6. API, autenticación, estados de error y ejemplo de solicitud/respuesta.
7. Prompt, tratamiento de contexto no confiable, fallback sin evidencia, citas y guard de cifras; límites de la técnica.
8. Threshold/min_score, medición de Recall@3 y protocolo de evaluación de fidelidad, incluidos alérgenos/monedas.
9. Compose Qdrant, persistencia/seguridad local, comandos de setup, test, evaluación y reinicio seguro.
10. Evidencias, resultados, riesgos residuales y decisión sobre futuras integraciones; explícitamente no LangChain/LlamaIndex/agentes en este hito.

## 11. Parámetros que bloquean configuración final

1. Acceso/documentación de los modelos estudiantiles aprobados de 4Geeks: **modelo, URL/ruta, protocolo, autenticación, dimensión de embeddings y límites** por separado para embedding y generación. No copiar secretos a documentación.
2. Confirmar si ambos modelos disponibles soportan español, si los embeddings pueden enviarse en batch, y si el generador soporta el contexto/tamaño de salida previstos.
3. Ejecutar calibración real para determinar `KNOWLEDGE_MIN_SCORE`; no asignar un número por intuición. Validar los chunks con los manuales fijados.
4. Confirmar si se requiere acceso host directo a Qdrant; predeterminado: sólo red Docker, persistencia por named volume y ninguna exposición pública.
5. Confirmar que el equipo acepta la base `main` actual y que el Hito 7 no depende de reabrir/apilar la PR #73 cerrada sin merge.

## 12. Primer paso y estimación

**Primer paso ejecutable al comenzar la implementación (no ejecutado en esta sesión):**

```bash
git fetch origin && git switch -c feature/rag-knowledge-base origin/main
```

Antes de integrar con modelos reales deben estar disponibles URL, IDs de modelo, mecanismo de autenticación, dimensión real de embeddings y límites/contexto. La clave se provee sólo por entorno. Sin ello pueden avanzar las copias fijadas, chunker, schemas, tests stub y Qdrant en memoria; setup/evaluación real quedan bloqueados.

Estimación orientativa, sin contar espera de acceso al proveedor: fase 0 (base y decisiones), 0,5 día; fases 1–2 (fuentes/configuración), 0,5–1 día; ingestión/embeddings/idempotencia, 1–1,5 días; recuperación, generación, API y pruebas, 1–1,5 días; Backoffice, 0,5–1 día; evaluación real, endurecimiento, documentación y evidencias, 1–2 días. **Total estimado: 4,5–7,5 días de ingeniería**, más el tiempo externo de habilitación de modelos y cualquier iteración necesaria para alcanzar Recall@3≥80%.