# RAG — plan del reinicio

Base verificada: main f18688e583aba6d912e4a887b17ec3baf2dd0806.
Rama ya creada en esta sesión: feature/rag-knowledge-base-restart.
Fuentes descargadas nuevamente del syllabus; no se recuperó código histórico.

1. Registrar baseline API/backoffice/typecheck/build antes de integrar RAG.
2. Corpus íntegro y procedencia en docs/company-knowledge-base y docs/rag/sources.json.
3. data/process: chunking semántico, configuración, HTTP de embeddings y setup idempotente.
4. data/pipelines: retrieve con umbral, generación independiente y query como composición.
5. Qdrant persistente en Compose; SDK qdrant-client con uv en services/api.
   httpx existente para modelos. Sin frameworks ni servicios de pago.
6. Router autenticado services/api/app/domains/knowledge; pantalla y cliente en uis/backoffice.
7. tests/pipelines/test_rag.py y tests API/UI sin red; evaluador independiente en data/eval.
8. Documentar validación, pendientes, walkthrough y borrador de PR sin publicar.

Aceptación: al menos 3 chunks autocontenidos por manual, payload oficial, IDs
UUID deterministas, limpieza limitada a puntos propios, incompatibilidad sin
recreación destructiva, respuesta generada incluso sin contexto, errores sanitizados,
UI protegida con carga y reintento, sin regresiones nuevas.

Estado final (19-oct-2026): integración real completada con Google Gemini
(`gemini-embedding-001` 768d float + `gemini-3.5-flash-lite`, soporte de clave única),
indexación idempotente de los 14 chunks en Qdrant real, calibración `RAG_MIN_SCORE=0.60`,
`Recall@3 = 16/16 (100.0%)`, auditoría humana de fidelidad aprobada (`19/19`) y recorrido
E2E multicapa verificado (`Backoffice :3001 → FastAPI :8000 → Qdrant :6333 → Gemini`).
