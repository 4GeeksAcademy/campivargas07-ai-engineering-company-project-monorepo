# Evaluación y entrega RAG — Brasaland

## Estado al 15 de octubre de 2026

Sesión iniciada el 14 y continuada el 15 de octubre (America/Mexico_City). **Hito abierto:** adaptadores y pruebas offline verificados; faltan configuración local, indexación/consulta con modelos reales, calibración del umbral, Recall@3, revisión de fidelidad y E2E real.

El usuario confirmó **Perplexity directo**. Se verificaron sus contratos documentados de [embeddings](https://docs.perplexity.ai/api-reference/embeddings-post) y [generación](https://docs.perplexity.ai/api-reference/agent-post). No se encontraron claves ni configuración RAG en el entorno de ejecución ni archivos `.env` locales inspeccionados. El acceso del editor no se interpreta como una clave API. No hubo llamadas a modelos reales ni se inventaron sus resultados.

Rama conservada: `feature/rag-knowledge-base`, dos commits sobre `origin/main` local `810a873`. Backup y dos stashes preservados; cambios existentes mantenidos y ampliados sólo dentro de RAG. Sin commit, push, merge ni PR. No se incorporaron proyectos de ventas/Redis/Celery.

## Antecedentes recibidos, no ejecutados de nuevo como tales

La sesión anterior reportó API 137 passed/5 skipped, corpus 3/3, pipeline/Qdrant local 5/5, Backoffice dirigido 12/12, lock/Compose/build Docker e imports correctos y Qdrant saludable. Son antecedentes. Los resultados de la sesión actual se listan aparte abajo; no se afirma que el Qdrant real haya sido indexado con modelos.

## Verificado en esta sesión

Todos los tests de modelos usan HTTP simulado; Qdrant en las pruebas de indexado es local en memoria.

| Comando | Resultado |
|---|---|
| `uv run --directory services/api --no-sync pytest -q -rs` | **250 passed, 5 skipped**, 36,73 s. |
| `services/api/.venv/bin/python -m pytest services/api/tests/test_knowledge_providers.py services/api/tests/test_knowledge_pipeline.py data/tests -q` | **128 passed**: 74 proveedores HTTP, 40 pipeline/Qdrant, 3 corpus y 11 evaluación. Los dos primeros grupos también están incluidos en la suite API; no sumar como pruebas distintas. |
| `npm --prefix uis/backoffice run test` | **112 passed**, 19 suites. |
| `npm --prefix uis/backoffice run lint -- src/lib/knowledge-api.ts src/test/knowledge-api.test.ts src/test/knowledge-assistant.test.tsx src/test/knowledge-route-protection.test.tsx` | PASS. |
| `uv lock --directory services/api --check --offline` | PASS, 57 paquetes; no fue necesario añadir dependencias. |
| `DATABASE_URL=postgresql://placeholder:placeholder@localhost/placeholder SECRET_KEY=nonsecret-validation-only docker compose config --quiet` | PASS; placeholders sólo para validar configuración, no para conectar una BD. |
| `docker build -f services/Dockerfile -t brasaland-rag-session .` | PASS, instalación con `--frozen`. Verificación final tras los cambios de generación y smoke. |
| Smoke de imagen sin red, corpus montado read-only | Cuatro documentos, 18 chunks (5/5/4/4), 18 casos del evaluador e imports de API/pipelines. |
| `python -m data.eval.run_evaluation --output /tmp/brasaland-rag-configuration-check-root-20261015.json` desde venv API | Exit 1 esperado: `blocked_configuration`, `hits`, `recall_at_3`, `meets_target` en `null`; cero llamadas externas. |
| `npm --prefix uis/backoffice run typecheck` | FAIL: tres errores idénticos a baseline; detalle abajo. |
| `npm --prefix uis/backoffice run build` | FAIL en rama y baseline al descargar Inter/Plus Jakarta Sans desde Google Fonts. No llegó al typecheck del build. |

En este entorno `uv` está en `/tmp/rag-uv-target/bin/uv`; se usó `UV_CACHE_DIR=/tmp/rag-uv-cache`, porque la caché global era read-only. La suite con TestClient se ejecutó con permiso fuera del sandbox: dentro quedaba bloqueada al iniciar el portal asyncio. No se cambiaron tests para ocultar ese bloqueo. Una repetición inicial encontró cuatro fallos en la nueva prueba por usar Qdrant como context manager; se corrigió la prueba y la suite final pasó. La revisión automática de aprobación tuvo un fallo temporal por límite de uso; la continuación se aprobó y ejecutó.

Logs locales de apoyo: `/tmp/brasaland-rag-api-tests-final.log`, `/tmp/brasaland-rag-docker-build-final.log`, `/tmp/brasaland-backoffice-audit.md`. Los comandos y resultados quedan registrados aquí para no depender de conservar `/tmp`.

### Cinco skipped y su impacto

Todos están en `services/api/tests/test_inventory_postgres.py`; la fixture exige `TEST_DATABASE_URL`, que no está configurada:

1. `test_pg_minimum_stock_check_constraint`: CHECK de stock mínimo no negativo.
2. `test_pg_entry_quantity_positive_constraint`: entradas estrictamente positivas.
3. `test_pg_exit_quantity_positive_constraint`: salidas estrictamente positivas.
4. `test_pg_foreign_key_constraint`: FK de ingrediente.
5. `test_pg_concurrent_outbound_movements_prevent_negative_stock`: bloqueo pesimista/concurrencia real para impedir stock negativo.

La suite restante usa SQLite/TinyDB temporales. Estos skipped impiden afirmar validación nativa de PostgreSQL y concurrencia, no omiten pruebas RAG. No se configuró una BD de producción para ejecutarlos ni se eliminaron pruebas.

## Corpus y conteo

Revisión fijada: `48e21bb4c45a4101abb09cff8e6e0ad941c87847`. El contexto contractual RAG es `docs/rag/CONTEXT-brasaland.es.md`, no el histórico de incidentes. Manuales conservados sin cambios.

| Fuente | Chunks procesados localmente |
|---|---:|
| loyalty-program | 5 |
| waste-protocol | 5 |
| menu-allergens | 4 |
| supplier-ordering | 4 |
| Total | **18** |

**Indexación con embeddings reales: pendiente.** Este conteo se obtuvo del chunker y se reprodujo en contenedor. Las pruebas de doble setup comprueban 18 puntos estables con embeddings simulados, no prueban una colección productiva. No se inspeccionó ni modificó una colección real para afirmar un conteo indexado.

## Recall@3: criterio y estado

Se conservan exactamente las 16 preguntas originales dentro del corpus y las dos fuera de alcance; cuatro por manual. `expected_evidence` añade extractos literales de los manuales, validados contra las fuentes antes de ejecutar.

Un acierto requiere que **cada hecho esperado**, con cifras, moneda, unidades y condiciones intactas, esté contenido en alguno de los primeros tres chunks de la fuente esperada. Las preguntas compuestas pueden necesitar varios chunks dentro del top-3. Sólo se normalizan mayúsculas y espacios/saltos de línea. Coincidir en documento o encabezado, hallar una cifra en otro contexto o recuperar la evidencia en rango 4/5 no cuenta.

`Recall@3 = aciertos in-scope / 16`. Objetivo ≥80%, es decir **al menos 13/16**. Los errores de recuperación cuentan como misses; los dos negativos quedan fuera del denominador. Se obtiene el mismo top-5 usado por `query`, se mide Recall en sus primeros tres y se conserva el top-5 completo para generación.

**Resultado real: no medido.** El caso de prueba offline de 13/16 sólo comprueba aritmética y control de flujo; no es un resultado del modelo. `KNOWLEDGE_MIN_SCORE` sigue sin valor operativo. El score COSINE no es probabilidad.

Para calibrar: guardar una recuperación diagnóstica sin descarte (`min_score=-1`, sólo experimento), observar evidencia acertada/perdida y scores de positivos/negativos, comparar candidatos de umbral con el mismo modelo/corpus y justificar el punto elegido que conserve al menos 13/16. No eliminar preguntas difíciles. Si los negativos y positivos se solapan, documentar la limitación y revisar chunking/modelo antes de afirmar el KPI.

## Fidelidad y generación: evaluación separada

**Resultado real: no medido.** El evaluador completo conserva pregunta, top-5, contexto exacto, respuesta, fallos por etapa y campos de revisión manual. Incluye ambas consultas fuera del corpus y una prueba adicional de instrucción maliciosa dentro del contexto, separada del Recall y de las 18 preguntas originales.

Revisar cada respuesta con revisor identificado y hallazgos: soporte de afirmaciones/citas, cifras y monedas sin conversión, condiciones/excepciones, advertencias de trazas/contaminación cruzada/Costilla BBQ, español y tono de vendedor, insuficiencia en los negativos y resistencia al ataque. Una cita o respuesta fluida no demuestra fidelidad. `faithfulness.measured_score` queda `null` hasta revisión documentada.

Las pruebas HTTP verifican signed INT8, dimensiones, no herramientas/preset, parsing, errores/timeouts/JSON malformado, contexto vacío pasando por el modelo, guard numérico, signos, promesas de riesgo y negaciones honestas. El rechazo produce un error, no una respuesta fija atribuida al generador. Son controles conservadores; no certifican fidelidad semántica ni resistencia al prompt injection. Ver política y límites en `rag-design.md`.

**Pregunta/respuesta real trazable: pendiente.** El smoke preparado pregunta “¿Cuántos puntos necesito para el nivel Oro y qué beneficios tiene?” y usa el manual de lealtad literal. No se publica aquí una respuesta simulada como si fuera real.

## Backoffice: situación precisa y baseline

Se verificaron mediante sesión/HTTP simulados: AuthGuard en carga/anónimo/autenticado, cliente real con Bearer hacia el rewrite, respuesta visible, carga accesible, bloqueo de doble envío, error y reintento conservando la pregunta. La prueba backend de recorrido conecta auth → router real → query/retrieve → Qdrant en memoria → adaptadores HTTP simulados → respuesta `{answer}`; cubre éxito, vacío, fallo de proveedor y rechazo de grounding. Esto es integración offline, **no E2E real con navegador y proveedor**.

Para comparar con la base se archivó `810a873` en `/tmp/brasaland-backoffice-baseline-1v_pj5hn`, sin checkout/reset/stash. Se enlazaron las mismas dependencias actuales (Next 16.2.10). Los siguientes tres archivos son idénticos al baseline y reproducen los mismos errores:

| Archivo / causa | Arreglo mínimo propuesto, sin aplicar |
|---|---|
| `src/lib/auth/context.tsx:72`: se lee `id` del envelope `{user,profile}` | Acceder al usuario anidado y confirmar el identificador contractual de telemetría. |
| `src/services/telemetry.ts:175`: la construcción genérica pierde correlación de la unión discriminada | Constructor tipado que preserve event_type/properties/entity_action, con sus pruebas; sin `any` ni suppressions. |
| `src/test/telemetry-service.test.ts:17`: mock genérico incompatible con `fetch` | `vi.fn<typeof fetch>` y Response válida. |

Build normal de rama/base: fallo de red descargando Inter y Plus Jakarta Sans. En la config temporal de baseline se ajustó sólo `turbopack.root: '/'` para resolver symlinks de las mismas dependencias; no se cambió la config del repo. Un intento adicional con webpack no aportó diagnóstico y no sustenta ninguna conclusión. Typecheck demuestra los errores de código; el build no llegó a ellos. No se cambiaron fuentes, auth ni telemetría ni se redujeron exigencias.

## Configuración local y comandos reales pendientes

Desde la raíz, completar `services/api/.env` a partir de la plantilla sin sobrescribir un archivo existente. No compartir claves en el chat:

- Embedding: `EMBEDDING_PROVIDER=perplexity`, `EMBEDDING_API_BASE_URL=https://api.perplexity.ai/v1`, `EMBEDDING_MODEL=pplx-embed-v1-0.6b`, `EMBEDDING_DIMENSIONS=1024`, `EMBEDDING_ENCODING_FORMAT=base64_int8`, **`EMBEDDING_API_KEY`**.
- Generación: `GENERATION_PROVIDER=perplexity`, `GENERATION_API_BASE_URL=https://api.perplexity.ai/v1`, **`GENERATION_API_KEY`**, **`GENERATION_MODEL`** con el ID habilitado obtenido por discovery. Puede usarse la misma clave en ambas variables si tiene permisos, sin asumirlo.
- Qdrant: Compose fija `QDRANT_URL=http://qdrant:6333`; `QDRANT_API_KEY` sólo si está habilitado. Se mantiene privado, sin puerto público.
- Recuperación: **`KNOWLEDGE_MIN_SCORE`** tras calibración; no asignarlo por intuición.
- Compose/API ya requiere `DATABASE_URL` y `SECRET_KEY` válidos. `TEST_DATABASE_URL` es sólo para una BD PostgreSQL desechable de pruebas.

No cambiar modelo/dimensión/codificación/preprocesamiento entre setup y consulta. Si ya existe una colección incompatible o sin metadata, el programa falla y pide migración explícita; no borrarla automáticamente.

```bash
# Discovery de modelos de generación: no usa Qdrant ni llama a generación.
uv run --project services/api --env-file services/api/.env --locked python -m data.process.smoke --list-generation-models

# Completar GENERATION_MODEL; levantar sólo servicios existentes del hito.
docker compose --env-file services/api/.env up -d --build qdrant backend

# Smoke real mínimo: embedding + generación con evidencia literal, sin búsquedas.
docker compose --env-file services/api/.env exec -T backend python -m data.process.smoke

# Ejecutar dos veces; los dos setup deben conservar IDs y conteos reales.
docker compose --env-file services/api/.env exec -T backend python -m data.process.setup
docker compose --env-file services/api/.env exec -T backend python -m data.process.setup

# Sólo diagnóstico de calibración; -1 NO es un umbral operativo recomendado.
docker compose --env-file services/api/.env exec -T -e KNOWLEDGE_MIN_SCORE=-1 backend python -m data.eval.run_evaluation --retrieval-only > /tmp/brasaland-retrieval-unfiltered.json

# Tras elegir con evidencia el umbral operativo: guardar candidatos en archivos distintos.
docker compose --env-file services/api/.env exec -T backend python -m data.eval.run_evaluation --retrieval-only > /tmp/brasaland-retrieval-calibrated.json
docker compose --env-file services/api/.env exec -T backend python -m data.eval.run_evaluation > /tmp/brasaland-rag-real.json

# Pregunta/respuesta real trazable una vez calibrado el entorno.
docker compose --env-file services/api/.env exec -T backend python -m data.pipelines.query '¿Cuántos puntos necesito para el nivel Oro?'
```

Después de cambiar `.env`, recrear el backend con `docker compose --env-file services/api/.env up -d backend` para aplicar su entorno. También se puede pasar el umbral candidato con `exec -e KNOWLEDGE_MIN_SCORE=...`. No sobrescribir evidencias de ejecuciones previas.

Inspección reproducible del store real, después de **cada** setup (guardar salidas en archivos distintos y comparar IDs):

```bash
docker compose --env-file services/api/.env exec -T backend python - <<'PY'
from collections import Counter
from data.process.qdrant_store import COLLECTION_NAME, create_client
c = create_client()
try:
    info = c.get_collection(COLLECTION_NAME)
    points, offset = [], None
    while True:
        batch, offset = c.scroll(COLLECTION_NAME, limit=100, offset=offset, with_payload=True, with_vectors=False)
        points.extend(batch)
        if offset is None:
            break
    required = {'company', 'source_document', 'section', 'language', 'chunk_index', 'text', 'embedding_configuration'}
    assert all(required <= p.payload.keys() for p in points)
    counts = Counter(p.payload['source_document'] for p in points)
    assert set(counts) == {'loyalty-program', 'waste-protocol', 'menu-allergens', 'supplier-ordering'}
    assert all(n >= 3 for n in counts.values())
    assert len({p.id for p in points}) == len(points) == c.count(COLLECTION_NAME, exact=True).count
    print({'collection': COLLECTION_NAME, 'vectors': str(info.config.params.vectors), 'count': len(points), 'sources': dict(counts), 'ids': sorted(str(p.id) for p in points)})
finally:
    c.close()
PY
```

Cerrar finalmente el E2E con sesión real en Backoffice → Knowledge → API autenticada → Qdrant/modelos → respuesta visible. Conservar sólo evidencia sin JWT/credenciales; confirmar HTTP `{answer}` y revisar fallos/carga/reintento. Adjuntar al informe los modelos/configuración no secreta, manifiesto del evaluador, fecha, conteo real, misses, threshold elegido y revisión manual; hasta entonces no cerrar el hito.
