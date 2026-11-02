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

La Parte 3 no está implementada en este hito.
