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


## Métricas estructuradas para arbitraje

`RfpMetadata.fields` puede incluir `rfp_metrics` (opcional) con:
- `procurement_cost_per_event_usd`
- `operations_implied_price_usd`
- `setup_days` (mínimo)
- `annual_value_usd`

Si faltan, `cost-vs-feasibility` queda `not_evaluable` y se registra pregunta abierta; no se asume OK. No se inventan importes: solo se usan si están presentes en los metadatos o se registran mediante la capa de datos.

## Mapeo de aprobadores

Los responsables (Camila, Felipe, Lucía, Jake, Mariana) se asocian a usuarios existentes mediante:
- Variable `RFP_APPROVER_MAP` (JSON: departamento -> lista de user_uuid), o
- Tabla `rfp_department_approver` gestionada por un administrador vía `POST /rfp-requests/approvers`.

No se crean cuentas ni credenciales en el repositorio; la identidad proviene del JWT.
