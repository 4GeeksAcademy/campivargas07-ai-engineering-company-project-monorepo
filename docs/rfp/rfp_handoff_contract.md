# RFP handoff contract

## Parte 1 → Parte 2

`RfpHandoff` (persistido en `rfp_handoff`):
- `ticket_id`
- `key_aspects`: lista de `{department, aspect, detail}`
- `workstreams`: lista de `{department, status}`. Define los departamentos activos.
- `prepared_at`, `consumed_at`, `consumed_by`

La Parte 2 consume únicamente tickets en `analisis_completo` con handoff presente.
Al iniciar, marca `consumed_at` y `consumed_by="rfp-response-generation"`.

## Parte 2 → Parte 3

`RfpGenerationHandoff` (persistido en `rfp_generation_handoff`):
- `ticket_id`
- `sections`: lista de `{department_id, draft_id, version, content, evaluation_result, approval_status="pendiente"}`
- `global_compliance`: `{pass, rule_ids, violations, details}`
- `open_questions`
- `requires_ceo_approval`
- `prepared_at`, `consumed_at`, `consumed_by`

La Parte 3 consume únicamente tickets con `RfpGenerationHandoff` presente (estados `en_evaluación` o `needs_human_review`).
Al iniciar, crea `RfpApprovalRun` con `thread_id=rfp-{ticket_id}` y marca el ticket `esperando_aprobación`.

## Parte 3 — aprobación humana y cierre

- `RfpApprovalRun`: estado del grafo, ciclo de corrección, conflictos, aprobación CEO, referencia al documento final.
- `RfpHumanApproval`: decisión tipada (`approve`/`reject`/`request_changes`) asociada a `ticket_id`, `department_id`, `version` exacta y `approver_uuid` del JWT.
- `RfpConflict`: triggers `cost-vs-feasibility`, `setup-sla-breach`, `ceo-threshold` con árbitro fijo.
- `RfpFinalDocument`: documento final ensamblado de versiones aprobadas, guardado en PostgreSQL con referencia de archivo.

Estados del ticket en Parte 3:
- `esperando_aprobación`: mientras exista revisión humana pendiente.
- `terminado`: solo cuando el documento final esté guardado y accesible.

`all_sections_approved` de Parte 2 refleja evaluación automática; no equivale a aprobación humana.