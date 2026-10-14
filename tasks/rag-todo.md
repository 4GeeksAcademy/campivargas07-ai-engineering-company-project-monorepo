# Tareas: Hito 7 — RAG y Base de Conocimiento

> Estado de ejecución: implementación parcial en `feature/rag-knowledge-base`. Las aceptaciones que requieren proveedor y evaluación calibrada permanecen pendientes.

- [x] R0 — Rama creada desde `origin/main`; PR #73 no incorporado. Proveedor real pendiente de confirmación.
- [x] R1 — Fuentes allowlisted y contexto RAG añadidos con revisiones fijadas; repetir comparación byte-a-byte al cierre.
- [ ] R2 — Compose y pyproject modificados; `uv.lock` no actualizado. Compose validado con placeholders; healthcheck real pendiente.
- [x] R3 — Loader/chunker/adaptador configurables añadidos; 4 fuentes generan 4–5 chunks y pruebas base pasan. Proveedor/dimensión reales pendientes.
- [ ] R4 — Implementación añadida, aún sin prueba contra Qdrant ni sincronización idempotente verificada.
- [ ] R5 — Pipelines añadidos; protocolo OpenAI-compatible provisional y evaluación real pendiente.
- [ ] R6 — Ruta autenticada añadida; faltan pruebas API dedicadas.
- [x] R7 — Vista, cliente y navegación añadidos; pruebas iniciales pasan. Typecheck reporta tres errores existentes en auth/telemetry.
- [ ] R8 — Set y runner añadidos (16 in-scope, 2 out-of-scope); Recall@3 y fidelidad real pendientes.
- [ ] R9 — Walkthrough, memoria y reportes pendientes; checks backend y lock pendientes.

- [ ] **R0 — Acordar base y proveedor**
  - Archivos: ninguno.
  - Dependencias: ninguna.
  - Acción: confirmar `origin/main` como base; recopilar documentación estudiantil 4Geeks y confirmar endpoint, modelo, autenticación, dimensiones y límites de embedding/generación.
  - Aceptación: decisiones registradas sin secretos. Crear `feature/rag-knowledge-base` desde `origin/main`; PR futura a `main` titulada `feat: rag knowledge base`.
  - Verificación: comparar SHA de rama con `origin/main`; comprobar que no incorpora commits exclusivos de `feature/regression-model-eval`/PR #73.

- [ ] **R1 — Fijar las fuentes oficiales**
  - Archivos: añadir `docs/rag/CONTEXT-brasaland.es.md` y los cuatro Markdown completos en `docs/company-knowledge-base/`.
  - Dependencias: R0.
  - Aceptación: contexto copiado con procedencia/revisión `bc4c7c86e09cc336317c7acba5a41a108925f4bb`; corpus íntegro desde revisión `48e21bb4c45a4101abb09cff8e6e0ad941c87847`; contextos generales e incidentes intactos.
  - Verificación: comparar cada archivo con blob oficial fijado; confirmar nombres, slugs y montos/caracteres sin normalización.

- [ ] **R2 — Configurar cliente y Compose**
  - Archivos: `services/api/pyproject.toml`, `services/api/uv.lock`, `services/api/.env.example`, `docker-compose.yml`; `services/Dockerfile` sólo si se necesita ajustar el contexto de build.
  - Dependencias: R0.
  - Aceptación: `qdrant-client` fijado a versión compatible, `httpx` reutilizado, variables separadas para Qdrant/embedding/generación; servicio Qdrant con named volume y acceso restringido; `data/` y corpus accesibles sin colisionar con `services/data`.
  - Verificación: revisar configuración efectiva sin revelar secretos; `docker compose config` y chequeo de arranque/persistencia cuando se implemente; lock consistente. No instalar durante la fase de planificación.

- [ ] **R3 — Implementar carga, embeddings y chunking**
  - Archivos: `data/__init__.py`, `data/process/__init__.py`, `data/process/loader.py`, `data/process/chunking.py`, `data/process/embeddings.py`.
  - Dependencias: R1, R2 y R0 (protocolo/modelo de embedding confirmado; chunking puede adelantarse con stub).
  - Aceptación: sólo cuatro documentos permitidos; `embed(text) -> list[float]` real compartido; al menos tres chunks autocontenidos por fuente; regla, cifras, moneda, condición y excepción permanecen juntas.
  - Verificación: pruebas unitarias de mapeo, estructura de chunks, advertencias y valores; embedding stub verifica shape/validación; llamada real de smoke test cuando existan credenciales.

- [ ] **R4 — Sincronizar Qdrant de forma idempotente**
  - Archivos: `data/process/qdrant_store.py`, `data/process/setup.py`.
  - Dependencias: R2–R3 y dimensión confirmada con embedding real.
  - Aceptación: colección `brasaland_knowledge`, payload mínimo exacto, compañía/idioma/slug, UUIDv5 determinista; dimensión obtenida del modelo; los chunks obsoletos de una fuente se eliminan; mismatch nunca recrea colección automáticamente.
  - Verificación: Qdrant en memoria; dos `setup()` producen mismos IDs; fuente reducida no deja IDs antiguos; embedding/colección de dimensión incompatible falla sin borrado.

- [ ] **R5 — Separar retrieval, generación y composición**
  - Archivos: `data/pipelines/__init__.py`, `data/pipelines/retrieval.py`, `data/pipelines/generation.py`, `data/pipelines/query.py`.
  - Dependencias: R3–R4 y modelo/protocolo de generación confirmado.
  - Aceptación: contratos exactos `retrieve(query, *, k=5, min_score) -> list[dict]`, `generate_answer(question, context) -> str`, `query(question) -> str`; 0..k resultados; contexto vacío responde falta de evidencia; cita documento; sin LangChain/LlamaIndex/agente.
  - Verificación: tests de umbral, menos de k, cero, retorno exacto del modelo y contexto; modelo simulado y caso de prompt injection; guard determinista para cifras sin soporte y moneda.

- [ ] **R6 — Añadir endpoint protegido**
  - Archivos: `services/api/app/domains/knowledge/__init__.py`, `schemas.py`, `router.py`, `services/api/app/main.py`, `services/api/tests/test_knowledge_api.py`.
  - Dependencias: R5.
  - Aceptación: `POST /knowledge/query` recibe `{"question":"..."}` y devuelve sólo `{"answer":"..."}`; usa `Depends(get_current_user)` y llama a `query()`.
  - Verificación: tests 401/200/schema/delegación/error; assert explícito de ausencia de payload, score, vector y resultados crudos.

- [ ] **R7 — Añadir consulta al Backoffice**
  - Archivos: `uis/backoffice/src/app/backoffice/knowledge/page.tsx`, `uis/backoffice/src/components/knowledge/KnowledgeAssistant.tsx` y CSS module, `uis/backoffice/src/lib/knowledge-api.ts`, `uis/backoffice/src/components/backoffice-header.tsx`, `uis/backoffice/src/app/globals.css`, tests Vitest.
  - Dependencias: R6.
  - Aceptación: ruta protegida `AuthGuard`, token de `authApi`, `POST /api/knowledge/query`, input/pregunta, carga, respuesta, error y retry; apariencia con preferencia clara/oscura usando tokens existentes.
  - Verificación: pruebas de UI/cliente; typecheck, lint y build de `uis/backoffice`; revisar contraste/responsive y que la UI no presente chunks/scores.

- [ ] **R8 — Evaluar corpus y fidelidad**
  - Archivos: `data/eval/test-queries.json`, `data/eval/run_evaluation.py`, `docs/rag/rag-design.md`, `docs/rag/rag-evaluation-report.md`.
  - Dependencias: R1–R7 y proveedor/modelos reales.
  - Aceptación: ≥8 preguntas, plan inicial de 16 in-domain (≥4 por fuente) más dos fuera de corpus; Recall@3 real ≥80%; registro de chunks recuperados, fuentes y scores; cifras/condiciones/advertencias respaldadas.
  - Verificación: ejecutar contra Qdrant y modelos reales; separar resultados mock/real; registrar fórmula, denominador, score threshold calibrado y fallos; prueba manual específica de monedas y alérgenos.

- [ ] **R9 — Cerrar hito y preparar entrega**
  - Archivos: `tasks/walkthrough.md`, `memory-bank/progress.md`, `docs/rag/rag-design.md`, `docs/rag/rag-evaluation-report.md`.
  - Dependencias: R1–R8.
  - Aceptación: diseño explica arquitectura/configuración/seguridad/reproducibilidad; evidencia de pruebas y evaluación; walkthrough y memoria reflejan el hito; título de PR `feat: rag knowledge base` hacia `main`.
  - Verificación: suite backend, Vitest, typecheck, lint, build, `docker compose config`, smoke test autenticado y revisión de `git diff --check`; inspección final de archivos y ausencia de secretos.