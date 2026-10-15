# Plan vigente — Hito 7: RAG y Base de Conocimiento

## Continuidad y alcance

Actualización 15 de octubre de 2026, continuación de la sesión iniciada el 14 (America/Mexico_City). Se conserva `feature/rag-knowledge-base` sobre el ref local `origin/main` (`810a873`), con dos commits RAG previos y cambios sin commit. No recrear la rama, repetir cherry-picks, aplicar stashes ni publicar sin autorización. Backup `backup/rag-knowledge-base-pr27` y dos stashes preservados. La comparación con la base se hizo sin cambiar el checkout.

El hito cubre únicamente cuatro manuales → embeddings → Qdrant → recuperación/generación → endpoint autenticado → Knowledge. No incorpora ventas, Redis/Celery, PR #25/#26/#27, frameworks RAG ni orquestación de agentes. `services/api` continúa siendo el backend activo. Los planes de inventario y otros hitos se preservan.

## Fuentes preservadas

Contrato del hito: `docs/rag/CONTEXT-brasaland.es.md`, revisión `bc4c7c86e09cc336317c7acba5a41a108925f4bb`. Las referencias genéricas a CONTEXT-empresa apuntan a ese archivo. El contexto de incidentes no se indexa.

Corpus oficial ya copiado y conservado íntegro, revisión `48e21bb4c45a4101abb09cff8e6e0ad941c87847`:

| Fuente | Archivo en `docs/company-knowledge-base/` | Origen fijado |
|---|---|---|
| loyalty-program | brasaland-loyalty-program.es.md | [Syllabus](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-loyalty-program.es.md) |
| waste-protocol | brasaland-waste-protocol.es.md | [Syllabus](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-waste-protocol.es.md) |
| menu-allergens | brasaland-menu-allergens.es.md | [Syllabus](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-menu-allergens.es.md) |
| supplier-ordering | brasaland-supplier-ordering.es.md | [Syllabus](https://github.com/4GeeksAcademy/ai-engineering-syllabus/blob/48e21bb4c45a4101abb09cff8e6e0ad941c87847/content/contexts/00-general-contexts/brasaland/brasaland-supplier-ordering.es.md) |

No modificar manuales, contextos protegidos, `infra/`, `mcps/` ni historial de hitos cerrados. No introducir lógica de negocio duplicada en la UI.

## Inspección y decisiones de esta continuación

El proveedor es **Perplexity directo**, confirmado por el usuario. No había configuración ni claves disponibles. Se inspeccionaron los adaptadores existentes antes de editarlos; suposiciones anteriores de compatibilidad OpenAI, retorno temprano sin generador y fallback silencioso no satisfacían el contrato.

Se reutiliza `httpx`: embeddings `/v1/embeddings` con base64 signed INT8 y COSINE; generación `/v1/agent` con modelo explícito, sin preset/herramientas y un solo paso. El modo compatible para un proxy queda opt-in y requiere su contrato confirmado; no se aplica INT8 a un proxy por suposición. No se asume acceso por tener un agente del editor. Documentación oficial y límites en `docs/rag/rag-design.md`.

La dimensión pasa a ser configuración explícita verificada contra cada respuesta. Setup/consulta comparten modelo, dimensión, codificación y preprocesamiento, registrados en payload; se rechaza una colección incompatible sin borrarla. La generación vacía se solicita al modelo y se verifica explícitamente; los rechazos de grounding producen error, nunca sustitución atribuida al modelo.

## Plan por fases y aceptación

| Fase | Estado / archivos | Aceptación y siguiente verificación |
|---|---|---|
| R0 — Base y continuidad | Verificada localmente; sin mutaciones Git | Mantener rama, backup, stashes y cambios locales; no publicar. |
| R1 — Corpus | Loader/chunker ya existentes, sin reconstrucción | 4 fuentes allowlisted, 18 chunks (5/5/4/4); todos los documentos ≥3. Hashes incluidos en manifiesto de evaluación. |
| R2 — Entorno | Dependencias/lock existentes sincronizados; `.env.example`, Compose y contexto Docker actualizados | Lock/config/build e imports verificados. Aprovisionar variables locales sin versionar secretos. |
| R3 — Adaptadores | `embeddings.py`, `provider_http.py`, `generation.py`, `smoke.py` | 74 tests HTTP offline: payload/auth, signo INT8, longitud/dimensión/no nulo, parsing, errores/timeouts, salidas malformadas. Pendiente smoke real y modelo habilitado. |
| R4 — Colección y setup | `setup.py`, `qdrant_store.py`, `retrieval.py` | 40 tests: idempotencia, stale chunks, COSINE/dimensión/configuración, metadata faltante, filtros/umbral/k. Pendiente doble setup y payload/conteo reales. |
| R5 — Composición | `query.py` y `build_context` compartido con evaluación | Mantener setup/embed/retrieve/generate_answer/query; recuperación 0..k, vacío por generador, sin retorno de chunks ni fallback silencioso. Integración offline en 4 escenarios. |
| R6 — API autenticada | Router/contrato original conservado; nuevas pruebas de recorrido | 250 pruebas API pasan, 5 PostgreSQL skipped explicadas. Éxito sólo `{answer}`; errores genéricos sin detalle interno. |
| R7 — Backoffice | Cliente robusto y pruebas de estados/ruta/sesión | 112 pruebas pasan y lint dirigido PASS. Errores de typecheck y build comparados con base; no modificar auth/telemetría sin ampliar alcance. E2E real pendiente. |
| R8 — Evaluación real | Dataset 16+2 preservado; evidencia textual, runner/manifiesto y revisión separados | 11 pruebas del evaluador pasan. Pendientes calibración, ≥13/16 aciertos reales, fidelidad de cifras/moneda/condiciones/alérgenos/negativos e inyección. |
| R9 — Entrega | Diseño, informe, tareas, memoria y walkthrough actualizados | Evidencia offline y borrador `feat: rag knowledge base` sin publicar. Hito abierto hasta R8 y E2E reales; typecheck/build sin ocultar errores. |

## Pendientes ejecutables en orden

1. Configurar claves locales de Perplexity y descubrir `GENERATION_MODEL` habilitado. No pedir ni publicar claves en el chat.
2. Ejecutar `data.process.smoke`, setup real dos veces e inspección de colección/payload/IDs/conteos. Una incompatibilidad requiere decisión de migración explícita; no borrar automáticamente.
3. Capturar scores diagnósticos y comparar thresholds sin cambiar el dataset; fijar `KNOWLEDGE_MIN_SCORE` por evidencia. Ejecutar Recall con objetivo ≥13/16.
4. Evaluar generación separadamente, registrar una pregunta/respuesta real con chunks, negativas y prueba adversarial; completar revisión manual de fidelidad.
5. Cerrar recorrido navegador/sesión → Knowledge → API → modelos/Qdrant → respuesta visible.
6. Resolver por alcance aprobado los fallos base de auth/telemetría y conectividad de fuentes si se exige build/typecheck íntegro. Las causas y arreglos mínimos propuestos están documentados; no se aplicaron suppressions/exclusiones.
7. Sólo con autorización futura, preparar commit/publicación/PR. La descripción se encuentra en el walkthrough; no se ha publicado.

Los comandos exactos, resultados actuales y cinco skipped están en `docs/rag/rag-evaluation-report.md`; la configuración no secreta y política de errores en `docs/rag/rag-design.md`. No repetir la instalación del cliente ni regenerar el lock sin un cambio de dependencias. No estimar cierre del KPI antes de disponer del proveedor y medirlo.
