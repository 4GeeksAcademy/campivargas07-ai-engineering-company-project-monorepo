# Informe del reinicio RAG

Fecha de trabajo: 15 de octubre de 2026, America/Mexico_City.
Base exacta: `f18688e583aba6d912e4a887b17ec3baf2dd0806`.

## Antecedentes

PR #28 reportó 129 pruebas API, 5 omitidas, 89 UI, 3 errores TypeScript y fallo
Google Fonts. Se reprodujo la línea base en esta sesión antes de integrar RAG.
No se usaron resultados del RAG anterior ni archivos recuperados de su historial.

## Resultados de esta sesión

- Corpus oficial descargado de nuevo; revisión y hashes en `sources.json`.
- 14 chunks preparados: lealtad 5, desperdicio 3, alérgenos 3, proveedores 3.
- Pipeline: pruebas offline con Qdrant en memoria y HTTP simulado.
- API: 140 passed, 5 skipped (baseline 129/5; 11 nuevas).
- Backoffice: 100 passed, 18 suites (baseline 89, 16 suites; 11 nuevas).
- Typecheck: mismos tres errores exactos del baseline, ninguno en los archivos RAG.
- Lint dirigido a todos los TS/TSX nuevos/modificados: aprobado. Lint global falla
  por dos `any` en `src/services/telemetry.ts:181,184`; archivo idéntico a f18688e.
- Build de backoffice: falla por descarga de Google Fonts, igual que el baseline.
- Compose validado con DATABASE_URL/SECRET_KEY ficticios sólo para interpolación.
- Qdrant responde `healthz check passed`; volumen de trabajo separado.
- Imagen Docker compilada; import de router y corpus de 14 chunks desde la imagen
  verificados. No hay `.env` bajo `/app` en la imagen de prueba.
- Qdrant desechable en puerto 16333: setup repetido conserva 14 puntos usando
  **vectores simulados**. Esto prueba integración/idempotencia, no calidad semántica.

Los cinco skipped son pruebas de inventario PostgreSQL por ausencia de
`TEST_DATABASE_URL`: stock mínimo no negativo, cantidades positivas de entrada
y salida, clave foránea y concurrencia real con bloqueo pesimista. SQLite no
sustituye esas garantías; no se modificó inventario para omitirlas.

## Evidencia con modelos reales

| Métrica | Estado |
|---|---|
| Acceso/API y IDs de 4Geeks | Pendientes de confirmación del profesor |
| Dimensión y codificación real | No configuradas |
| Chunks indexados con embeddings reales | No ejecutado |
| Reindexación con embeddings reales | No ejecutada |
| Umbral calibrado | Pendiente |
| Recall@3, objetivo >=13/16 | No medido |
| Fidelidad de generación | No evaluada |
| Pregunta/respuesta real trazable | No disponible |
| Recorrido completo con modelos reales | Pendiente |

El usuario autorizó continuar con proveedores simulados mientras confirma el
acceso de estudiante. No se usaron claves personales ni servicios de pago.
No hay un porcentaje de recall o fidelidad atribuible a los mocks.

## Revisión de fidelidad a ejecutar

Para cada respuesta del evaluador, registrar aprobado/fallo y evidencia exacta:
1. Toda cifra, porcentaje, monto y unidad aparece respaldada en el contexto.
2. COP/USD y condiciones se conservan, sin conversiones automáticas.
3. Alérgenos: advertencia de contaminación cruzada y excepción BBQ presentes
   cuando correspondan; ninguna promesa de ausencia de riesgo.
4. Preguntas fuera de corpus: insuficiencia explícita, sin hechos inventados.
5. Instrucción maliciosa en contexto: no cambia las reglas ni introduce un 99%
   ficticio o promesas de seguridad.

El prompt y sus pruebas sólo acreditan el contrato enviado; no el comportamiento
de un modelo real. Ejecutar los comandos de `rag-design.md`, conservar resultados
y completar esta tabla antes de declarar el hito cerrado.

## Cierre del alcance simulado — 16 de octubre de 2026

A solicitud del usuario, el entregable se cierra localmente en modo simulado, sin
esperar el contrato de 4Geeks. La evidencia offline ya registrada arriba cubre los
contratos de proveedor, las regresiones API/UI, el setup repetido con vectores
simulados y el recorrido del navegador con proveedor simulado.

Este cierre no convierte en resultados las métricas de modelos reales: Recall@3,
fidelidad, calibración semántica y smoke tests reales permanecen sin medir. La
evidencia se conserva tal como fue registrada; no se volvió a ejecutar en esta
sesión. El usuario no proporcionó URL, autenticación ni modelos reales. No se hizo
commit, push ni PR.

## Continuación autorizada y evidencias nuevas — 16 de octubre de 2026

El pedido posterior de iniciar implementación reabre los pendientes; el cierre
simulado anterior se conserva como historial, no como aceptación del hito real.

- Base recién comprobada: API 129 passed/5 skipped, Backoffice 89, Website 4.
- Checkout recién comprobado: pipeline 47 passed, API 142 passed/5 skipped;
  Backoffice 107, Website 4. Las pruebas adicionales cubren igualdad con el
  umbral, rechazo de usuarios inactivos/tokens inválidos y contrato del cliente.
- Typecheck/lint global conservan exactamente los errores de base. El build
  actual compila y falla en `AuthMeResponse.id`, igual que el baseline con
  Webpack; el antiguo bloqueo de Google Fonts no se reprodujo ahora.
- PostgreSQL, navegador, imagen Docker y Qdrant servidor no se validaron en esta
  ejecución. Compose config y lint dirigido sí pasan.

Se detectó un pendiente en `data/eval/run.py`: `--generate` usa los mismos tres
chunks de Recall@3, mientras que `query()` utiliza hasta cinco. Antes de evaluar
fidelidad, separar ambos contextos y registrar el contexto de generación con
`k=5`. Copilot bloqueó la edición del módulo por exclusión de `data/`, por lo que
esa corrección sigue pendiente. No hay métricas reales nuevas ni declaración de
cierre; se requiere habilitar la edición y confirmar el acceso de 4Geeks.
