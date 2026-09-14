# Contexto del Agente de Inventario

## Alcance
Extender `services/api` con un dominio de inventario que soporte una arquitectura de doble base de datos:
- TinyDB para usuarios, autenticación, perfiles y proveedores existentes.
- Supabase/PostgreSQL mediante SQLModel para el catálogo de ingredientes y órdenes de movimiento de inventario.

## Reglas Clave
1. `current_stock` nunca se almacena ni se modifica como una columna; se calcula dinámicamente como:
   $$\text{current\_stock} = \sum(\text{inbound.quantity}) - \sum(\text{outbound.quantity})$$
2. `local_id` es obligatorio en endpoints que devuelvan un único `current_stock`.
3. Las entradas y salidas preservan el UUID estable del usuario autenticado en TinyDB.
4. Las salidas de inventario usan bloqueo pesimista atómico (`SELECT ... FOR UPDATE`). Si el saldo es insuficiente, se rechaza con `400 Bad Request` sin persistir nada.
5. Sin consultas N+1 en listados (número constante de consultas $O(1)$).
6. Siembra idempotente usando los 7 ingredientes de `src/demo.ts` y movimientos para `MED-001` y `MIA-001`.
7. Cero modificaciones a archivos `.env`; únicamente mantener actualizado `services/api/.env.example`.
8. Documentación obligatoria de cada hito: almacenar el `walkthrough.md` en la carpeta `tasks/` para mantener la trazabilidad de cada incremento técnico.
