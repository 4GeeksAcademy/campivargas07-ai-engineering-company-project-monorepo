# Plan de Implementación: Dominio de Inventario en Brasaland

## Visión General
Extender `services/api` con un dominio de inventario que soporte una arquitectura de doble base de datos (TinyDB para autenticación, usuarios y proveedores existentes; Supabase/PostgreSQL mediante SQLModel para catálogo de ingredientes y órdenes de movimiento de inventario). El stock se calcula dinámicamente como $\sum(\text{inbound}) - \sum(\text{outbound})$, nunca se persiste como columna, y se particiona por restaurante (`local_id`).

## Fases de Ejecución

- [x] **Fase 1: Auditoría del Baseline y Reconciliación de Dependencias**
  - Actualizar `services/api/pyproject.toml` con dependencias de ejecución y desarrollo.
  - Crear `services/api/.env.example` sin secretos.
  - Verificar que `.gitignore` excluya todas las variantes de `.env`.
  - Ejecutar `uv sync` en `services/api`.

- [x] **Fase 2: Rutas Base y Registro del Router de Incidencias**
  - Verificar todos los routers en `services/api/app/main.py`: auth, users, profiles, suppliers, incidents, inventory, health.
  - Garantizar que las pruebas existentes en `services/api/tests/test_incidents_api.py` pasen sin regresiones.

- [x] **Fase 3: UUID Estable para Usuarios de TinyDB y Backfill**
  - Añadir la rutina idempotente `backfill_users_uuid()` en `database.py`.
  - Actualizar `create_user` en `services/api/app/domains/users/service.py` para persistir `uuid = str(uuid.uuid4())`.
  - Actualizar los schemas `UserResponse` y `UserOut` para incluir `uuid: str | None = None`.
  - Mantener el claim `sub` del JWT como `str(user.doc_id)` para retrocompatibilidad total.
  - Asegurar que `get_current_user` siempre devuelva al usuario con su campo `uuid`.

- [x] **Fase 4: Motor SQLModel y Gestión de Sesiones**
  - Configurar `DATABASE_URL` exclusivamente vía variables de entorno en `services/api/app/database.py`.
  - Implementar el generador de sesiones por petición `get_db() -> Generator[Session, None, None]`.
  - Implementar `init_db()` importando previamente los modelos del dominio.
  - Conectar `init_db()` y `backfill_users_uuid()` al ciclo de vida `lifespan` de FastAPI.

- [x] **Fase 5: Modelos de Dominio, Constraints y Tablas**
  - Implementar `services/api/app/domains/operations/inventory/models.py`:
    - `Ingredient`: `id` (UUID PK), `sku` (único indexado), `name`, `category`, `unit_of_measure`, `minimum_stock >= 0`, `perishable`, `created_at` (UTC).
    - `IngredientEntry`: `id` (UUID PK), `ingredient_id` (FK), `local_id`, `quantity > 0`, `user_uuid`, `created_at` (UTC).
    - `IngredientExit`: `id` (UUID PK), `ingredient_id` (FK), `local_id`, `quantity > 0`, `user_uuid`, `created_at` (UTC).
    - CheckConstraints e índices sobre SKU, ingredient_id, local_id, user_uuid y created_at.

- [x] **Fase 6: Schemas Pydantic**
  - Implementar `services/api/app/domains/operations/inventory/schemas.py`:
    - Separación estricta de los modelos ORM de SQLModel.
    - `IngredientCreate`, `IngredientResponse`, `IngredientWithStockResponse`.
    - `InboundOrderCreate`, `OutboundOrderCreate`, `OrderResponse`, `OrderListResponse`.

- [x] **Fase 7: Endpoints de Productos (`local_id` Obligatorio)**
  - Implementar `GET /inventory/products?local_id=...` y `GET /inventory/products/{id}?local_id=...`.
  - Exigir `local_id` como parámetro obligatorio de consulta (`Query(...)`).
  - Implementar `POST /inventory/products` con validación de unicidad de SKU.

- [x] **Fase 8: Entradas de Inventario Autenticadas**
  - Implementar `POST /inventory/orders/inbound` guardando `current_user["uuid"]`.

- [x] **Fase 9: Salidas Transaccionales y Bloqueo de Concurrencia**
  - Implementar `POST /inventory/orders/outbound` con bloqueo de fila `SELECT ... FOR UPDATE` sobre `Ingredient`.
  - Verificar `current_stock >= requested_quantity`; rechazar con `HTTP 400` sin persistir si el saldo es insuficiente.

- [x] **Fase 10: Historial de Órdenes sin N+1**
  - Implementar `GET /inventory/orders` con número constante de consultas ($O(1)$) mediante joins / carga eager.

- [x] **Fase 11: Siembra Idempotente de Datos**
  - Implementar `seed.py` validando un usuario real en TinyDB, sembrando `ING-001` a `ING-007` y movimientos para `MED-001` y `MIA-001`.

- [x] **Fase 12: Suite Completa de Pruebas**
  - Crear `services/api/tests/conftest.py` con fixtures de SQLite en memoria (`PRAGMA foreign_keys=ON`).
  - Crear `services/api/tests/test_inventory_domain.py` cubriendo todos los requisitos funcionales y unitarios.
  - Crear `services/api/tests/test_inventory_postgres.py` con pruebas de integración y concurrencia real en PostgreSQL vía `TEST_DATABASE_URL`.

- [x] **Fase 13: Documentación y Verificación**
  - Actualizar `tasks/todo.md`, `tasks/walkthrough.md` y `memory-bank/progress.md`.
  - Verificación final de que toda la suite de pruebas esté verde.
