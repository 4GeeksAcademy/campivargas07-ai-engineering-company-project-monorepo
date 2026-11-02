# Contrato WebSocket — Chat del Manager support agent (Parte 2 de 2)

## Endpoint

- `POST /chat/sessions` (JWT) crea sesión.
- `WS /chat/ws?session_id=...&token=...` (o primer frame `auth`).
- Auth timeout: 5 s. No se envían eventos de chat antes de autenticar.

## Eventos

Envelope: `{"event": "...", "data": {...}}`

- `session_snapshot`
- `user_message`
- `token_chunk`
- `interrupt_requested`
- `generation_interrupted`
- `generation_completed`
- `error`

## Identidad

`session_id` es el mismo valor usado como LangGraph `thread_id` y `conversation_id`. No se crean identidades paralelas.

## Garantías

- Streaming real del proveedor (no se divide una respuesta completa).
- Validación incremental + holdback + validación final.
- Cancelación propaga al stream HTTP del proveedor.
- Pub/sub en memoria por proceso, un productor por sesión.
- Reconexión con backoff y snapshot.