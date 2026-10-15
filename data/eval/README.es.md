# Carpeta `data/eval`

Esta carpeta está orientada a **evaluación y validación**: datasets de evaluación, “golden sets”, resultados de experimentos, métricas, y artefactos usados para medir calidad de modelos, RAG, agentes o pipelines.

- **Propósito principal**: centralizar los insumos y salidas de evaluación para asegurar mejoras medibles a lo largo de los hitos del proyecto.
- **Recomendación**: documenta cada set de evaluación (qué mide, cómo se construyó, criterios de éxito) y evita incluir datos sensibles; si es necesario, usa datos sintéticos o anonimizados.

## Evaluación RAG de Brasaland

`test-queries.json` conserva 16 preguntas dentro del corpus (cuatro por manual) y dos fuera de alcance. `expected_evidence` contiene extractos literales de los manuales fijados; el runner comprueba que cada extracto exista en su fuente antes de consultar proveedores.

Un acierto exige que **todos** los extractos esperados aparezcan intactos en los tres primeros chunks recuperados de la fuente esperada. Una pregunta compuesta puede requerir varios chunks. Sólo se normalizan mayúsculas y espacios/saltos de línea; cifras, moneda, unidades y condiciones deben coincidir. El título y `expected_section` son referencias descriptivas: no demuestran evidencia por sí mismos. Un extracto en rango 4 o 5 no cuenta para Recall@3. Los fallos de recuperación cuentan como misses y el denominador sigue siendo 16; el objetivo exige al menos 13 aciertos.

Desde la raíz, con las dependencias API y las variables del proveedor exportadas en el entorno local:

```bash
services/api/.venv/bin/python -m data.eval.run_evaluation --retrieval-only --output /tmp/brasaland-retrieval-01.json
services/api/.venv/bin/python -m data.eval.run_evaluation --output /tmp/brasaland-rag-01.json
```

El modo completo obtiene el mismo top-5 y usa el mismo `build_context` que `query`; calcula Recall con los tres primeros y conserva el contexto exacto entregado al generador. Incluye las dos preguntas fuera del corpus en la captura de generación y un experimento adicional con una instrucción maliciosa insertada en un chunk de lealtad. Este experimento queda separado de las 18 preguntas y de Recall.

Cada JSON registra fecha UTC, configuración no secreta, modelos, dimensión/codificación, umbral, revisión/hashes del corpus, chunks/hashes locales, hashes de código/dataset, versiones, resultados, respuestas y fallos por etapa. Omite claves, URLs de endpoints y mensajes de excepciones para evitar filtrar secretos. La ejecución sin configuración queda `blocked_configuration`, sin llamadas y con métricas `null`. El CLI devuelve código 1 si está bloqueado, hay errores o Recall no alcanza el objetivo, y nunca sobrescribe un archivo existente.

**Fidelidad se revisa aparte:** completar `manual_review` por caso con revisor y hallazgos al contrastar afirmaciones y citas con `generation_context`. Verificar cifras, COP/USD sin conversión, condiciones/excepciones, advertencias de alérgenos, insuficiencia en ambos casos fuera del corpus y resistencia al experimento malicioso. El indicador `attack_marker_present` ayuda a detectar un ataque obvio; no es una prueba completa de fidelidad. `faithfulness.measured_score` permanece `null` hasta una revisión documentada. Los errores de generación o grounding quedan como errores, sin una respuesta de reemplazo atribuida al modelo.

Para calibrar `KNOWLEDGE_MIN_SCORE`, guardar ejecuciones de recuperación en archivos distintos con el mismo corpus, modelo, dimensión y codificación. Comparar misses, scores de positivos y ambos negativos; justificar el umbral elegido en el informe RAG. Un score no representa una probabilidad. No presentar una ejecución inyectada como KPI real: se etiqueta `offline_fixture`.

Pruebas sin servicios externos:

```bash
python3 -m unittest data.tests.test_evaluation -v
```
