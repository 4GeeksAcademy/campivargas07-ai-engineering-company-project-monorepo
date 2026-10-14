# Informe de evaluación RAG — Brasaland

## Resultado

**Estado: evaluación real pendiente.** No se configura en el repositorio un proveedor/modelo aprobado ni credenciales, por lo que no se generaron embeddings ni se consultó Qdrant real. No se afirma Recall@3, precisión o fidelidad grounded como resultado medido.

## Dataset

`data/eval/test-queries.json` contiene 18 casos: 16 consultas con fuente/sección objetivo (4 por cada manual) y 2 consultas fuera de corpus. La métrica de recuperación excluye explícitamente los dos casos fuera de alcance.

## Procedimiento reproducible

1. Confirmar y provisionar de forma segura el endpoint/modelo de embedding y generación, el protocolo, dimensiones y versión.
2. Actualizar el lock: `cd services/api && uv lock`.
3. Configurar variables requeridas localmente, levantar Qdrant/API y ejecutar el indexado (`python -m data.process.setup` desde el entorno cuyo `PYTHONPATH` incluya el paquete raíz, una vez configurado el endpoint).
4. Ejecutar `python data/eval/run_evaluation.py` con acceso al mismo Qdrant y embedding.
5. Revisar los 16 top-3, errores por fuente/sección y confirmar Recall@3 >= 0.80.
6. Evaluar manualmente las respuestas generadas en cifras, moneda, condiciones, advertencias de alérgenos, consultas fuera del corpus y resistencia a prompt injection.

## Definición

`Recall@3 = número de consultas in-scope donde al menos uno de los tres resultados recuperados coincide con fuente Y sección objetivo / 16`. El score vectorial no se interpreta como confianza. `KNOWLEDGE_MIN_SCORE` debe calibrarse con estos resultados y casos negativos; no se fija un umbral sin datos.

## Smoke tests disponibles

- `python -m unittest discover -s data/tests -v`: tests locales de corpus/chunking, distribución del dataset y guard numérico (no involucra proveedor externo).
- Pendientes: ejecución real del runner, evaluación de generación con respuestas de referencia, reporte de fallos y pruebas con monedas/alérgenos; actualizar este documento con timestamp, revision de corpus, embedding/generation model IDs, threshold y resultados agregados, sin incluir secretos.
