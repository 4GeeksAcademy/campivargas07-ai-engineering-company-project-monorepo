# Tareas vigentes — RAG y Base de Conocimiento

Estado al 15 de octubre de 2026: implementación y verificaciones offline completadas; hito abierto por modelos reales y E2E. Rama preservada con cambios locales, sin commit/publicación. Proveedor confirmado: Perplexity directo.

## Verificado previamente

- [x] Base local `origin/main` `810a873` y dos commits RAG portados antes de esta continuación; backup y stashes conservados.
- [x] Cuatro manuales oficiales y contexto RAG con procedencia/revisión fijadas; endpoint y pantalla Knowledge ya implementados.
- [x] Antecedentes registrados: API 137/5 skipped, corpus 3, pipeline 5, UI dirigida 12, lock/Compose/Docker/Qdrant saludable. No confundirlos con nuevas ejecuciones.

## Verificado en esta sesión

- [x] R0/R1 — Inspección de rama, cambios locales, memoria, reglas y documentos. Sin cambios de rama/stashes ni manuales; corpus local 18 chunks: 5/5/4/4.
- [x] R2 — Lock sincronizado sin añadir dependencias, Compose válido y build/imports de imagen; contexto Docker incluye process/pipelines/evaluación y excluye secretos.
- [x] R3 — Perplexity directo: contrato signed base64 INT8, dimensión/finitud/no nulo y generación tipada sin tools/preset; 74 pruebas HTTP offline.
- [x] R4 — Configuración vectorial persistida/validada, no recrear colecciones incompatibles, setup idempotente/stale chunks y retrieval 0..k; 40 pruebas.
- [x] R5 — Vacío por generador, rechazo explícito de grounding sin sustitución, contexto compartido query/evaluación; recorrido HTTP simulado en cuatro escenarios.
- [x] R6 — Suite API completa: 250 passed, 5 skipped de PostgreSQL por `TEST_DATABASE_URL` ausente; sin pruebas RAG omitidas.
- [x] R7 offline — Backoffice 112 pruebas, lint dirigido PASS; carga/error/reintento, AuthGuard/Bearer y respuesta visible con HTTP simulado.
- [x] R7 diagnóstico — Typecheck reproduce tres errores de `810a873`; build de base/rama falla descargando Google Fonts antes de typecheck. Causas/arreglos mínimos documentados, sin modificar auth/telemetría.
- [x] R8 herramientas — 16 preguntas dentro +2 fuera conservadas; criterio de evidencia textual completa en top-3, manifiesto reproducible, fidelidad separada y probe adversarial; 11 pruebas del evaluador y 3 de corpus pasan.
- [x] R9 parcial — Diseño, evaluación, plan, memoria y walkthrough actualizados; borrador `feat: rag knowledge base` conservado sin publicar.

## Pendiente o bloqueado

- [ ] Configurar localmente claves Perplexity, modelo de generación habilitado y entorno Qdrant; no compartir secretos en chat.
- [ ] Smoke real de embeddings/generación; confirmar modelo/dimensión/contratos en la cuenta, no sólo documentación.
- [ ] Setup Qdrant real dos veces; verificar colección, metadata, ≥3 chunks/manual, IDs y ausencia de duplicados. No borrar colecciones incompatibles.
- [ ] Calibrar `KNOWLEDGE_MIN_SCORE` con scores observados y negativos.
- [ ] Recall@3 real ≥80% (≥13/16), sin eliminar casos difíciles ni contar mocks.
- [ ] Revisar fidelidad real: cifras/monedas/condiciones, advertencias de alérgenos, insuficiencia fuera del corpus e inyección de contexto.
- [ ] Registrar pregunta/respuesta real con chunks y manifiesto, modelos, fecha y fallos.
- [ ] E2E real navegador/sesión → Knowledge → API → Qdrant/modelos → respuesta.
- [ ] Decidir alcance separado para fallos base de typecheck y descarga de fuentes, antes de modificar auth/telemetría/layout.
- [ ] Cierre del hito y cualquier commit/push/PR sólo tras resultados reales y autorización correspondiente.

Procedimientos exactos y evidencias: `docs/rag/rag-evaluation-report.md`. Ninguna casilla offline sustituye los pendientes reales.
