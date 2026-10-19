# RAG — estado del reinicio

## Cierre solicitado: alcance completamente simulado

El usuario pidió cerrar el proyecto en modo simulado sin esperar el contrato de
4Geeks. El cierre aplica sólo al recorrido offline/mock y no afirma calidad de
embeddings ni generación reales.

- [x] Pipeline, API, pantalla, corpus, almacenamiento y evaluación reproducible preparados.
- [x] Pruebas offline con proveedores simulados: API 140 passed/5 skipped y Backoffice 100 passed.
- [x] Setup repetido contra Qdrant desechable conservó 14 puntos usando vectores simulados.
- [x] Recorrido de navegador con proveedor simulado verificó login, respuesta, error y reintento.
- [x] Compose e imagen Docker verificados según la evidencia ya registrada en el informe.

La evidencia anterior corresponde a validaciones registradas antes de esta sesión;
no se repitió aquí. No se atribuyen métricas de Recall@3, fidelidad o calibración
semántica a los mocks.

## Integración real y validación E2E completadas (19-oct-2026)

- [x] Configurar proveedor real Google Gemini (`gemini-embedding-001` 768d float y `gemini-3.5-flash-lite`) con soporte de clave única en `data/process/config.py`.
- [x] Ejecutar smoke check (`data.process.smoke`) y reindexar de forma idempotente los 14 chunks reales en Qdrant (`data.process.rag` x2: `indexed: 14, removed: 0`).
- [x] Separar `Recall@3` (`k=3`) y `generation_context` (`k=5`) en `data/eval/run.py`.
- [x] Calibrar `RAG_MIN_SCORE=0.60`, medir `Recall@3 = 16/16 (100.0%)` (objetivo >=13/16) y auditar manualmente la fidelidad de las 19 salidas reales (`data/eval/rag-evaluation-01.json` y `docs/rag/rag-evaluation-report.md`).
- [x] Verificar recorrido E2E completo con servicios reales (`Backoffice :3001 → Proxy /api/knowledge/query → FastAPI :8000 → Qdrant :6333 → Gemini`) con sesión autenticada y preguntas en alcance y fuera de alcance.
