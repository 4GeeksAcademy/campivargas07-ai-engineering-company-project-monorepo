# Contrato SSE — Notificaciones de nuevas RFP (Parte 1 de 2)

## Evento

```
event: rfp_ticket_created
id: <event_row_id>
data: {"ticket_id":"...","client_name":"...","location":"...","service_type":"...","status":"analyzing","created_at":"...","departments_needed":[...]}
```

- Sin sobre anidado `{"event","data"}`.
- Sin PDF, secciones completas, secretos ni datos innecesarios.

## Identidad

El BRIEFING menciona `rfp_id`. En este repositorio **no existe** una entidad/ID separado: la identidad es `RfpTicket.id` (`ticket_id`, UUID). No se inventa `rfp_id` ni se duplica entidad. Mapeo: `rfp_id` (BRIEFING) ↔ `ticket_id` (repo).

## Estados

No se renombran estados internos. Mapeo interno → payload SSE:

- `analizando` → `analyzing`
- `analisis_completo` → `intake_complete`
- `generando_borrador` → `drafting`
- `en_evaluación` → `under_evaluation`
- `esperando_aprobación` → `waiting_for_approval`
- `terminado` → `done`
- `descartado` → `discarded`

El evento de esta parte se emite con `status = "analyzing"`.

## Momento de publicación

En `process_rfp_ticket`, inmediatamente después de persistir metadata y clasificación, solo si `is_rfp == True`. Antes de persistir resultados departamentales/síntesis/handoff. RFP descartada no genera evento válido.

## Distribución y recuperación

- Tabla durable `rfp_ticket_event` (cursor `id` autoincremental) con constraint único `(ticket_id, event_type)`.
- Cada stream consulta por cursor; funciona entre procesos sin Redis.
- `Last-Event-ID` para replay; si el cursor es inválido/vencido, se reconcilia con `GET /rfp-requests`.
- Dedupe por `ticket_id` en servidor y cliente.
- Heartbeat cada 15 s; cabeceras `text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

## Autorización

JWT del backoffice. Cada cliente recibe solo eventos cuyo `submitted_by_uuid` coincide con el usuario o rol `admin`. Token vencido cierra el stream.

## Preguntas de diseño

- **2 vs 50 conexiones:** comparten event loop, pool de PostgreSQL y tabla; carga proporcional al número de conexiones e intervalo de polling.
- **Por qué SSE:** unidireccional, HTTP estándar, reconexión automática, simple detrás de proxies.
- **Cuándo otro canal:** chat/comunicación bidireccional de baja latencia (Parte 2, WebSocket).