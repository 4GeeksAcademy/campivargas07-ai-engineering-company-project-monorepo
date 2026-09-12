# Walkthrough: Dominio de Inventario con SQLModel y Doble Base de Datos en `services/api`

Se ha completado la extensión de `services/api` con el dominio de inventario para Brasaland, integrando PostgreSQL mediante SQLModel sin alterar el funcionamiento previo de TinyDB, preservando la autenticación existente y cumpliendo rigurosamente todas las reglas de negocio y restricciones técnicas.

---

## 1. Resumen de Cambios Implementados

### 1.1 Configuración, Entorno y Dependencias
- **`services/api/pyproject.toml`**: Reconciliación completa de dependencias de ejecución (`sqlmodel`, `psycopg2-binary`, `pydantic`, `python-dotenv`, `tinydb`, `bcrypt`, `python-jose`, `fastapi`, `uvicorn`, `python-multipart`) y desarrollo (`pytest`, `pytest-cov`, `httpx`). Configuración de paquete para `setuptools` y registro del marker `postgres`.
- **`services/api/.env.example`**: Plantilla creada sin secretos reales (`DATABASE_URL`, `TEST_DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Seguridad**: No se crearon ni modificaron archivos `.env`. Las conexiones a base de datos se leen estrictamente del entorno.

### 1.2 Doble Base de Datos y Ciclo de Vida
- **`services/api/app/database.py`**:
  - TinyDB permanece intacto para `users`, `profiles` y `suppliers`.
  - Configuración del motor SQLModel leyendo `DATABASE_URL` exclusivamente de `os.environ`.
  - Generador de sesión por petición `get_db()`.
  - Rutina `backfill_users_uuid()` que asigna UUIDs estables deterministas (`uuid5`) a los usuarios existentes en TinyDB sin alterar el `doc_id`.
  - Función `init_db()` que importa los modelos ORM antes de ejecutar `SQLModel.metadata.create_all(engine)`.
- **`services/api/app/main.py`**:
  - `lifespan` handler que ejecuta `backfill_users_uuid()` e inicializa tablas SQLModel en el arranque.
  - Registro de los 7 routers del sistema: `auth_router`, `users_router`, `profiles_router`, `suppliers_router`, `incidents_router`, `inventory_router` y `health`.

### 1.3 Retrocompatibilidad de Autenticación y Usuarios (TinyDB)
- **`services/api/app/domains/auth/dependencies.py`**:
  - `get_current_user` continúa resolviendo al usuario por el `doc_id` del claim `sub` del JWT (contrato intacto).
  - Incluye fallback defensivo para asegurar que el diccionario `user_doc` siempre posea el campo `uuid`.
- **`services/api/app/domains/users/service.py`**:
  - `create_user` genera y persiste un UUID v4 (`uuid.uuid4()`) en TinyDB.
  - `_doc_to_response` expone `uuid` junto con `id: str` (el `doc_id`).
- **`services/api/app/domains/users/schemas.py`** y **`services/api/app/domains/auth/schemas.py`**:
  - `UserResponse` y `UserOut` incorporan el campo opcional `uuid: str | None = None` sin romper compatibilidad previa.

### 1.4 Modelos ORM, Schemas y Transacciones de Inventario
- **`services/api/app/domains/operations/inventory/models.py`**:
  - `Ingredient`: `id` (UUID PK), `sku` (único indexado), `name`, `category` (con constraint de categorías válidas), `unit_of_measure`, `minimum_stock` (Numeric $\ge 0$), `perishable` (bool), `created_at` (UTC con timezone). **Sin columna persistida de stock.**
  - `IngredientEntry`: `id` (UUID PK), `ingredient_id` (FK a `ingredient.id`), `local_id`, `quantity` (Numeric $> 0$), `user_uuid` (UUID indexado del creador), `created_at` (UTC).
  - `IngredientExit`: `id` (UUID PK), `ingredient_id` (FK a `ingredient.id`), `local_id`, `quantity` (Numeric $> 0$), `user_uuid` (UUID indexado del creador), `created_at` (UTC).
  - CheckConstraints nativos de PostgreSQL: `minimum_stock >= 0`, `quantity > 0`.
- **`services/api/app/domains/operations/inventory/schemas.py`**:
  - Schemas Pydantic independientes (`IngredientCreate`, `IngredientResponse`, `IngredientWithStockResponse`, `InboundOrderCreate`, `OutboundOrderCreate`, `OrderResponse`, `OrderListResponse`).
- **`services/api/app/domains/operations/inventory/repository.py`**:
  - Cálculo dinámico de stock: $\sum(\text{inbound}) - \sum(\text{outbound})$ por `local_id`.
  - Consultas constantes $O(1)$ sin N+1 para listados de productos y órdenes con JOINs a `Ingredient`.
  - Salidas atómicas con bloqueo pesimista `SELECT ... FOR UPDATE` sobre la fila del ingrediente. Validación de saldo antes de insertar; si no alcanza, aborta con rollback sin persistir nada.
- **`services/api/app/domains/operations/inventory/service.py`**:
  - Lógica de negocio y traducción de errores (`400 Bad Request` en saldo insuficiente, `404 Not Found` en ingrediente inexistente, `409 Conflict` en SKU duplicado).
- **`services/api/app/domains/operations/inventory/router.py`**:
  - Expone los 6 endpoints bajo `/inventory`:
    - `GET /inventory/products?local_id=...` (`local_id` obligatorio $\to 422$ si falta).
    - `POST /inventory/products` (201, autenticado).
    - `GET /inventory/products/{id}?local_id=...` (`local_id` obligatorio $\to 422$ si falta).
    - `POST /inventory/orders/inbound` (201, autenticado, guarda `user_uuid`).
    - `POST /inventory/orders/outbound` (201, autenticado, bloqueo transaccional, guarda `user_uuid`).
    - `GET /inventory/orders` (autenticado, consultas constantes, sin N+1).

### 1.5 Siembra Idempotente
- **`services/api/app/domains/operations/inventory/seed.py`**:
  - Valida que el identificador del usuario (`--user`) corresponda a un usuario real en TinyDB; si no existe, aborta.
  - Siembra los 7 ingredientes de `src/demo.ts` (`ING-001` a `ING-007`).
  - Siembra movimientos para `MED-001` y `MIA-001` obteniendo exactamente el saldo neto de `demo.ts` ($8$ para `ING-001` en `MED-001`, $25$ para `ING-002`, $3$ para `ING-003`, $45$ para `ING-001` en `MIA-001`, $10$ para `ING-006`).
  - Totalmente idempotente: en ejecuciones subsiguientes no duplica ingredientes ni movimientos.

---

## 2. Evidencias de Validación

### 2.1 Batería Completa de Pruebas Unitarias y de Integración (65 pruebas verdes)
Ejecución en `services/api`:
```bash
TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/brasaland_api_test" uv run pytest
```
Resultado:
```text
============================= test session starts ==============================
collected 65 items

tests/test_auth_dependency.py ......                                     [  9%]
tests/test_incidents_api.py ...                                          [ 13%]
tests/test_inventory_domain.py ...............                           [ 36%]
tests/test_inventory_postgres.py .....                                   [ 44%]
tests/test_login.py ......                                               [ 53%]
tests/test_me.py .........                                               [ 67%]
tests/test_password_service.py .........                                 [ 81%]
tests/test_register.py .....                                             [ 89%]
tests/test_token_service.py .......                                      [100%]

======================== 65 passed, 1 warning in 17.39s ========================
```

### 2.2 Cobertura de Código en el Dominio de Inventario (94%)
Ejecución:
```bash
TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/brasaland_api_test" uv run pytest tests/test_inventory_domain.py tests/test_inventory_postgres.py --cov=app.domains.operations.inventory --cov-report=term-missing
```
Resultado:
```text
Name                                             Stmts   Miss  Cover   Missing
------------------------------------------------------------------------------
app/domains/operations/inventory/__init__.py         0      0   100%
app/domains/operations/inventory/models.py          40      0   100%
app/domains/operations/inventory/repository.py      85      4    95%   92, 158, 208, 233
app/domains/operations/inventory/router.py          35      1    97%   44
app/domains/operations/inventory/schemas.py         65      0   100%
app/domains/operations/inventory/seed.py            73     14    81%   119, 130-132, 223-237, 245
app/domains/operations/inventory/service.py         44      1    98%   69
------------------------------------------------------------------------------
TOTAL                                              342     20    94%
======================== 20 passed, 1 warning in 5.60s =========================
```

### 2.3 Validación de Concurrencia en PostgreSQL
En `tests/test_inventory_postgres.py::test_pg_concurrent_outbound_movements_prevent_negative_stock`:
- Saldo inicial: 10.0 unidades en `MED-001`.
- Dos hilos concurrentes intentan retirar 7.0 unidades cada uno.
- El bloqueo `SELECT ... FOR UPDATE` serializa ambas transacciones.
- Exactamente 1 hilo obtiene éxito (consumo 7.0) y el otro hilo falla con `InsufficientStockError (HTTP 400)`.
- El saldo final resultante es estrictamente 3.0 (nunca negativo).

