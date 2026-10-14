# Diseño técnico — Base de conocimiento RAG de Brasaland

## Estado y alcance

Implementación inicial del hito 7 en `feature/rag-knowledge-base`. El corpus se limita a cuatro manuales oficiales en español copiados desde syllabus revision `48e21bb4c45a4101abb09cff8e6e0ad941c87847`: lealtad, desperdicio, alérgenos y pedidos a proveedores. El contexto específico del hito está en `CONTEXT-brasaland.es.md` con la revisión documentada en su encabezado. No se indexan contextos de incidentes ni documentos fuera de la allowlist.

La ruta de consulta no puede ofrecer respuestas funcionales hasta configurar el endpoint/modelo de embeddings, endpoint/modelo de generación, dimensiones del vector y un umbral de similitud calibrado. Los adaptadores HTTP actuales son provisionales y asumen rutas compatibles con OpenAI (`/embeddings` y `/chat/completions`); deben verificarse contra la documentación aprobada antes del despliegue. No se incluye ni se inventa ningún secreto o modelo.

## Arquitectura

1. `data/process/loader.py` lee exclusivamente `docs/company-knowledge-base/` y los cuatro nombres permitidos.
2. `chunking.py` agrupa contenido por encabezado y límites de párrafo para conservar listas, advertencias, cifras y condiciones. Cada fuente produce actualmente al menos tres chunks; tamaños y agrupación son una heurística inicial pendiente de evaluación cualitativa.
3. `embeddings.py` genera vectores por HTTP y verifica que sean finitos, numéricos y de la dimensión configurada.
4. `setup.py` crea IDs UUIDv5 deterministas, metadata con fuente/sección/idioma/empresa y hashes, crea una colección cosine sin recrear una colección incompatible, hace upsert y elimina chunks obsoletos.
5. `retrieval.py` consulta como máximo k resultados y aplica `KNOWLEDGE_MIN_SCORE`, que debe calibrarse; un score de similitud no es probabilidad ni confianza.
6. `generation.py` entrega contexto como datos no confiables, instruye al modelo a contestar en español sólo con evidencia y devuelve una respuesta de insuficiencia si no hay contexto. Un guard lexical conservador comprueba cifras y unidades numéricas, pero no garantiza por sí solo fidelidad semántica.
7. FastAPI expone `POST /knowledge/query`, protegido por `get_current_user`, y serializa únicamente `{answer}`. Backoffice usa la ruta protegida `/backoffice/knowledge`, la sesión existente y muestra carga/error/respuesta sin exponer scores ni chunks.

## Infraestructura y configuración

Compose añade `qdrant/qdrant:v1.19.2`, almacenamiento persistente nombrado y sin puerto publicado en el host. El API usa `qdrant-client==1.19.1`; `httpx` ya existente realiza llamadas a los proveedores. Las fuentes y el paquete `data/` se montan read-only en el backend. Variables y placeholders se listan en `services/api/.env.example`; hay que actualizar `services/api/uv.lock` con uv antes de construir con `--frozen`.

Variables requeridas: `EMBEDDING_API_BASE_URL`, `EMBEDDING_MODEL`, opcional `EMBEDDING_API_KEY`; `GENERATION_API_BASE_URL`, `GENERATION_MODEL`, opcional `GENERATION_API_KEY`; `KNOWLEDGE_MIN_SCORE` calibrado; `QDRANT_URL` y opcional `QDRANT_API_KEY`. Los límites de timeout/token son configurables. Las claves se deben provisionar sólo en el entorno local/secret manager, nunca versionar.

## Seguridad y límites

- Autorización heredada del JWT actual; no se agregan permisos a datos de clientes.
- Corpus estático allowlisted, sin carga de documentos por petición.
- Qdrant sólo es accesible por red privada Compose.
- Prompt injection en el contexto se trata como contenido, no instrucción; aun así, hace falta prueba adversarial con el modelo real.
- El error del proveedor se registra en backend y al usuario sólo se devuelve un 503 genérico.
- El validador numérico sólo detecta cadenas de cifras/unidades; probar monedas, unidades, advertencias y expresiones cualitativas con evaluación manual.

## Reproducibilidad y evaluación

`data/eval/test-queries.json` mantiene 16 preguntas in-scope (cuatro por fuente) y dos fuera de alcance. `run_evaluation.py` calcula Recall@3 por coincidencia de fuente y sección esperadas y registra los resultados top-3. Debe ejecutarse sólo tras poblar Qdrant con el modelo aprobado; el objetivo del hito es Recall@3 >= 0.80. El informe de evaluación debe registrar modelo/revisión, threshold, denominador, fallos y revisión manual de fidelidad, monedas y alérgenos. No se reporta aquí un KPI real porque no están provisionados los endpoints/modelos aprobados.

## Validaciones realizadas

- `python -m unittest discover -s data/tests -v`: 3 pruebas pasan; cada uno de los cuatro documentos genera de 4 a 5 chunks.
- `docker compose config --quiet` con valores placeholder no secretos para las variables obligatorias: pasa.
- `python -m compileall -q data services/api/app/domains/knowledge services/api/app/main.py`: pasa.
- Dos pruebas Vitest añadidas sobre API y componente: 5 pruebas pasan.
- `npm run typecheck` completo actualmente falla en tres archivos ajenos a esta entrega (`src/lib/auth/context.tsx`, `src/services/telemetry.ts`, `src/test/telemetry-service.test.ts`).
- Qdrant real, generación/embeddings real, tests FastAPI, build/lint completo, uv lock y Recall@3 real aún no validados.
