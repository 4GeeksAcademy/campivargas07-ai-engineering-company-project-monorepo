# RAG de Brasaland — reinicio desde f18688e

## Estado y fuentes

Implementación nueva en `feature/rag-knowledge-base-restart`, sin restaurar el RAG
retirado. Corpus y contexto descargados del repositorio oficial 4Geeks Academy,
revisión `b0489cb8eeba892b15aaae88b5341a326d546b9a`.
[SOURCES](sources.json) registra URLs inmutables y SHA-256 de cada manual.
[Contexto RAG](CONTEXT-brasaland.es.md) es una copia íntegra; el contexto histórico
de incidentes en `docs/CONTEXT-brasaland.es.md` no se modificó.

El 19 de octubre de 2026 se completó la integración y validación E2E con modelos
reales utilizando los endpoints compatibles con OpenAI de **Google Gemini**
(`gemini-embedding-001` a `768` dimensiones en formato `float` y
`gemini-3.5-flash-lite` para generación controlada sin herramientas externas).

## Responsabilidades

```text
4 manuales → load_chunks → setup → embed → Qdrant
sesión → /backoffice/knowledge → /api/knowledge/query (proxy)
       → FastAPI /knowledge/query → query
       → retrieve → embed → Qdrant → generate_answer → respuesta visible
```

- `data/process/corpus.py`: corpus explícito y bloques semánticos.
- `data/process/embeddings.py`: HTTP, decodificación y validación de vectores.
- `data/process/rag.py`: `setup()` ejecutable e idempotente.
- `data/process/store.py`: cliente Qdrant y compatibilidad de colección.
- `data/pipelines/rag.py`: `retrieve`, `generate_answer`, `query` separados.
- `services/api/app/domains/knowledge/router.py`: autenticación existente,
  validación y traducción segura de errores; importa `query`, no duplica lógica.
- `uis/backoffice`: cliente con `authApi.getToken()`, proxy existente, AuthGuard,
  formulario accesible, estado de carga, cancelación al desmontar y reintento.

`data/` es un paquete local editable `brasaland-knowledge`, declarado en el
proyecto uv de `services/api`. No confundirlo con `services/data/` (TinyDB).
No se añadió un servidor dentro de `data/`, ni API dentro de las UIs.

## Fragmentación

| Manual | Chunks | Unidad conservada |
|---|---:|---|
| loyalty-program | 5 | Acumulación/vigencia, niveles completos, redención, transferencia, FAQ |
| waste-protocol | 3 | Registro+procedimiento+excepciones juntos, escalamiento, metas |
| menu-allergens | 3 | Platos con advertencias, protocolo completo, certificación BBQ con protocolo |
| supplier-ordering | 3 | Responsable/horario, frecuencias completas, stock+recargo+aprobación juntos |

Son **14 chunks semánticos verificados e indexados en Qdrant con embeddings reales**
(`gemini-embedding-001`, 768 dimensiones). No se divide
por caracteres ni por líneas. Las listas completas conservan sus condiciones.
El título original acompaña cada bloque. En alérgenos se repiten advertencias
para que ningún chunk aislado omita el protocolo de contaminación cruzada o
la excepción de certificación de la Costilla BBQ. El loader falla si cambia
la estructura de párrafos: revisar el agrupamiento antes de aceptar otro corpus.
Los tests verifican hashes oficiales y cobertura de todas las líneas del corpus.

Payload: `company=brasaland`, `source_document` con slug oficial, `section`,
`language=es`, `chunk_index`, `text`, más `managed_by=brasaland-rag-restart-v1`.
IDs UUIDv5 estables por propietario/documento/índice. La colección se llama
exactamente `brasaland_knowledge`, distancia COSINE. Su vector nombrado incluye
una huella del endpoint, modelo, dimensión, codificación y preprocesamiento
(`strip-v1`), rechazando cambios de contrato incluso con igual dimensión.

`setup` valida la colección existente antes de embeber; prepara todos los vectores
antes de escribir; hace upsert y luego elimina sólo IDs obsoletos previamente
identificados con filtros `company` y `managed_by`. No recrea colecciones
incompatibles ni elimina puntos de otro propietario. Ejecutar un solo indexador
a la vez; no es un protocolo de migración concurrente ni una transacción entre
varias operaciones Qdrant. Si falla una escritura, repetir setup con el mismo corpus.

## Contrato configurable de modelos

Contrato activo: `RAG_HTTP_CONTRACT=embeddings-chat-v1`, validado con los endpoints
compatibles con OpenAI de Google Gemini (`https://generativelanguage.googleapis.com/v1beta/openai/embeddings`
y `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions`).

- Autenticación Bearer, endpoints completos HTTPS (HTTP sólo para pruebas locales).
  Si el proveedor utiliza una sola clave de API para embeddings y generación (como
  Google Gemini), basta con definir `RAG_EMBEDDING_API_KEY` (o `RAG_API_KEY` /
  `GEMINI_API_KEY`) y `settings()` la reutiliza automáticamente para ambos servicios.
- Embeddings: POST `{model,input:[text],dimensions,encoding_format}`;
  respuesta `{model,data:[{index:0,embedding:...}]}` (acepta respuestas de un solo
  elemento donde el proveedor omita `"index"`). Se verifica modelo,
  cantidad, dimensión, valores finitos y vector no nulo. `float` exige lista
  numérica; `base64_int8` exige base64 válido decodificado como int8 **con signo**.
  No se admite binario empaquetado ni conversión silenciosa entre formatos.
- Generación: POST `{model,stream:false,tool_choice:"none",messages}`;
  respuesta `choices[0].message.content` de tipo string no vacío, con
  `finish_reason="stop"`. Se rechazan truncamientos, refusals y tool calls.
  No se envían herramientas ni se ejecuta ninguna búsqueda externa.
- Timeout acotado y errores de transporte/HTTP/JSON convertidos a `ProviderError`.
  Sin reintentos invisibles en producción ni respuestas fijas atribuidas al modelo.

Configuración calibrada en `services/api/.env.example`:
- `RAG_EMBEDDING_MODEL=gemini-embedding-001` (`RAG_EMBEDDING_DIMENSION=768`, `RAG_EMBEDDING_ENCODING=float`)
- `RAG_GENERATION_MODEL=gemini-3.5-flash-lite`
- `RAG_MIN_SCORE=0.60` (calibrado experimentalmente sobre las 18 consultas de evaluación:
  las 16 consultas en corpus puntúan entre `0.6170` y `0.7751`, y las fuera de corpus
  en el set de prueba puntúan $\le 0.5637$). Documentos y consultas pasan por
  el mismo `embed` y el mismo preprocesamiento.

## Respuesta y seguridad de la integración

`retrieve(query, *, k=5, min_score)` devuelve diccionarios y puede devolver menos
de k o cero. Aplica umbral en Qdrant y comprueba de nuevo los scores recibidos.
`query` siempre llama a `generate_answer`, también con contexto vacío. El prompt
pide español, voz de vendedor entrenado, cifras/monedas/condiciones originales,
insuficiencia honesta y documentos tratados como datos. No convierte COP/USD.
No existe sustitución posterior de la salida; el prompt **no demuestra fidelidad**.

El endpoint devuelve sólo `{answer}`. 401/403 usa autenticación existente;
422 valida pregunta no vacía, máximo 2000 caracteres y sin campos adicionales;
502 indica fallo del proveedor y 503 configuración/almacén no disponible.
Los mensajes internos no se envían al cliente. La UI representa la respuesta
como texto React, sin interpretar HTML del modelo. Los estilos usan variables
de tema existentes; no se cambian pantallas ni reglas de autenticación anteriores.

## Ejecución reproducible

Desde la raíz del repositorio, con `uv` instalado:

```bash
uv sync --project services/api --extra dev
uv lock --project services/api --check
uv run --project services/api --extra dev python -m pytest tests/pipelines/test_rag.py
uv run --directory services/api --extra dev pytest -q -rs
npm --prefix uis/backoffice run test
npm --prefix uis/backoffice run typecheck
npm --prefix uis/backoffice run lint
npm --prefix uis/backoffice run build
```

Completar localmente `services/api/.env` usando `.env.example` y colocando la clave
de Gemini en `RAG_EMBEDDING_API_KEY` (no es necesario duplicarla en `RAG_GENERATION_API_KEY`
ya que el cargador de configuración la reutiliza automáticamente si pertenecen al mismo
proveedor). No enviar claves al chat ni versionar `.env`.
`QDRANT_URL` local apunta a `http://127.0.0.1:6333`.

```bash
# Compose requiere además DATABASE_URL y SECRET_KEY ya existentes en el entorno.
docker compose config --quiet
docker compose up -d qdrant
docker compose build backend
# Smoke check, indexación real idempotente y evaluación completa:
uv run --project services/api --env-file services/api/.env python -m data.process.smoke
uv run --project services/api --env-file services/api/.env python -m data.process.rag
uv run --project services/api --env-file services/api/.env python -m data.process.rag
uv run --project services/api --env-file services/api/.env python -m data.eval.run --generate --delay 4.5 --output /tmp/rag-evaluation-01.json
```

El comando `data.process.rag` ejecuta realmente `setup`. En Compose se pasan
variables RAG al backend; su archivo de interpolación es `.env` de la raíz o
un `--env-file` explícito. No basta con editar el `.env` de API para que Compose
lo use. No se cambia la configuración real de PostgreSQL ni se borran volúmenes.

Docker usa contexto raíz con allowlist `services/Dockerfile.dockerignore` que
excluye `.env*`, cachés y entornos. `/app/api` sigue siendo la API; `/app/data`
sigue reservado a los datos anteriores; `/data` contiene el paquete RAG y
`/docs/company-knowledge-base` el corpus, montados de sólo lectura en desarrollo.
Qdrant 1.16.3 y SDK 1.16.2; volumen `brasaland-knowledge-storage`, puerto publicado
sólo en loopback `127.0.0.1:6333`, sin puerto gRPC publicado. No se despliega a Internet.

## Evaluación ejecutada

`data/eval/test-queries.json`: 16 preguntas dentro del corpus y 2 fuera de alcance.
Una pregunta cuenta como acierto si **un mismo chunk** entre los tres recuperados
(`Recall@3`) contiene todas las evidencias esperadas y pertenece al documento correcto.
No basta con coincidir en documento o encabezado. Objetivo: al menos 13/16.
Los casos fuera de alcance no entran en el denominador.

Cuando se ejecuta con `--generate`, el evaluador recupera `k=5` para
`generation_context` (idéntico al flujo real de `data.pipelines.rag.query`) y evalúa
`Recall@3` sobre los primeros 3 resultados (`all_retrieved[:3]`). El resultado
completo y sanitizado (sin claves ni secretos) se encuentra en
[rag-evaluation-01.json](../../data/eval/rag-evaluation-01.json) y su auditoría
humana línea por línea en [rag-evaluation-report.md](rag-evaluation-report.md),
alcanzando **Recall@3 = 16/16 (100.0%)** y **19/19 respuestas fieles**.
