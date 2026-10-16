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

## Diferido fuera del alcance simulado

- Confirmar el contrato, autenticación y modelos habilitados de 4Geeks.
- Probar embeddings/generación reales y reindexar con esos vectores.
- Calibrar `RAG_MIN_SCORE`, medir Recall@3 (objetivo >=13/16) y revisar fidelidad
  con salidas reales. Estas métricas siguen sin medirse y no se simulan como resultados.
- Registrar la pregunta/respuesta real trazable y recorrido completo con modelos reales.

## Publicación

- No se hizo commit, push ni PR. Requieren autorización explícita aparte.
