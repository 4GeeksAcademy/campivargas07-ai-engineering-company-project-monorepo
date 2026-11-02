# RFP approval and final document (Parte 3)

## Checkpoints

- Thread principal: `rfp-{ticket_id}`.
- Checkpointer persistente: `PostgresSaver` si `DATABASE_URL` es PostgreSQL; `SqliteSaver` a archivo en desarrollo/pruebas.
- Reanudación con `Command(resume={interrupt_id: decision})` sobre el mismo thread, sin reinvocar desde la entrada.

## Interrupts independientes

- Fan-out paralelo con `Send` por departamento activo (+ rama `ceo` si aplica).
- Cada rama invoca `interrupt()` con borrador, versión, evaluación, incidencias y preguntas abiertas.
- Reanudar una rama no bloquea a las demás (validado por pruebas).

## Arbitraje

Triggers estructurados:
- `cost-vs-feasibility` (Camila Ospina)
- `setup-sla-breach` (Felipe Guerrero; Camila escala)
- `ceo-threshold` (Mariana Restrepo)

Los agentes señalan conflictos; no los resuelven por consenso libre. Si faltan métricas estructuradas, el conflicto queda `not_evaluable` y se registra pregunta abierta.

## Correcciones

- Solo se regeneran las secciones afectadas (generadores/evaluadores de Parte 2).
- Límite de ciclos (default 3). Al agotarse: salida explícita `agotado` y ticket `needs_human_review`.

## Documento final

- Formato Markdown ensamblado determinísticamente a partir de versiones aprobadas.
- Guardado en PostgreSQL (`rfp_final_document`) + referencia de archivo.
- Idempotente: no se duplica por reintentos.