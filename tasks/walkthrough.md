# Walkthrough: Dominio de Inventario con SQLModel y Doble Base de Datos en `services/api`

Se ha implementado la extensión de `services/api` con el dominio de inventario para Brasaland, integrando PostgreSQL mediante SQLModel junto con TinyDB, preservando la autenticación existente y documentando las interfaces y validaciones.

---

## 1. Resumen de Cambios Implementados

### 1.1 Configuración, Entorno y Dependencias
- **`services/api/pyproject.toml`**: Reconciliación de dependencias de ejecución (`sqlmodel`, `psycopg2-binary`, `pydantic`, `python-dotenv`, `tinydb`, `bcrypt`, `python-jose`, `fastapi`, `uvicorn`, `python-multipart`) y desarrollo (`pytest`, `pytest-cov`, `httpx`). Configuración de paquete para `setuptools` y registro del marker `postgres`.
- **`services/api/.env.example`**: Plantilla sin secretos reales (`DATABASE_URL`, `TEST_DATABASE_URL`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`).
- **Seguridad**: No se versionan archivos con contraseñas o tokens. Las conexiones a base de datos se leen del entorno.

### 1.2 Doble Base de Datos y Ciclo de Vida
- **`services/api/app/database.py`**:
  - TinyDB para `users`, `profiles` y `suppliers` (ruta parametrizable vía `SUPPLIERS_DB_PATH`).
  - Configuración del motor SQLModel leyendo `DATABASE_URL` exclusivamente de `os.environ`.
  - Generador de sesión por petición `get_db()`.
  - Rutina `backfill_users_uuid()` que asigna UUIDs estables deterministas (`uuid5`) a los usuarios existentes en TinyDB sin alterar el `doc_id`.
  - Función `init_db()` que importa los modelos ORM antes de ejecutar `SQLModel.metadata.create_all(engine)`.
- **`services/api/app/main.py`**:
  - `lifespan` handler que ejecuta `backfill_users_uuid()` e inicializa tablas SQLModel en el arranque.
  - Registro de los 7 routers del sistema: `auth_router`, `users_router`, `profiles_router`, `suppliers_router`, `incidents_router`, `inventory_router` y `health`.
  - Middleware CORS estándar sin acoplamientos regex.

### 1.3 Retrocompatibilidad de Autenticación y Usuarios (TinyDB)
- **`services/api/app/domains/auth/dependencies.py`**:
  - `get_current_user` continúa resolviendo al usuario por el `doc_id` del claim `sub` del JWT.
  - Incluye fallback defensivo para asegurar que el diccionario `user_doc` siempre posea el campo `uuid`.
- **`services/api/app/domains/users/service.py`**:
  - `create_user` genera y persiste un UUID v4 (`uuid.uuid4()`) en TinyDB.
  - `_doc_to_response` expone `uuid` junto con `id: str` (el `doc_id`).
- **`services/api/app/domains/users/schemas.py`** y **`services/api/app/domains/auth/schemas.py`**:
  - `UserResponse` y `UserOut` incorporan el campo opcional `uuid: str | None = None`.

### 1.4 Modelos ORM, Schemas y Transacciones de Inventario
- **`services/api/app/domains/operations/inventory/models.py`**:
  - `Ingredient`: `id` (UUID PK), `sku` (único indexado), `name`, `category` (con constraint de categorías válidas), `unit_of_measure`, `minimum_stock` (Numeric $\ge 0$), `perishable` (bool), `created_at` (UTC con timezone). **Sin columna persistida de stock.**
  - `IngredientEntry`: `id` (UUID PK), `ingredient_id` (FK a `ingredient.id`), `local_id`, `quantity` (Numeric $> 0$), `user_uuid` (UUID indexado del creador), `created_at` (UTC).
  - `IngredientExit`: `id` (UUID PK), `ingredient_id` (FK a `ingredient.id`), `local_id`, `quantity` (Numeric $> 0$), `user_uuid` (UUID indexado del creador), `created_at` (UTC).
  - CheckConstraints nativos de PostgreSQL: `minimum_stock >= 0`, `quantity > 0`.
- **`services/api/app/domains/operations/inventory/schemas.py`**:
  - Schemas Pydantic (`IngredientCreate`, `IngredientResponse`, `IngredientWithStockResponse`, `InboundOrderCreate`, `OutboundOrderCreate`, `OrderResponse`, `OrderListResponse`).
- **`services/api/app/domains/operations/inventory/repository.py`**:
  - Cálculo dinámico de stock: $\sum(\text{inbound}) - \sum(\text{outbound})$ por `local_id`.
  - Consultas constantes $O(1)$ sin N+1 para listados de productos y órdenes con JOINs a `Ingredient`.
  - Salidas atómicas con bloqueo pesimista `SELECT ... FOR UPDATE` sobre la fila del ingrediente. Validación de saldo antes de insertar; si no alcanza, aborta con rollback sin persistir nada.
- **`services/api/app/domains/operations/inventory/service.py`**:
  - Lógica de negocio y traducción de errores (`400 Bad Request` en saldo insuficiente, `404 Not Found` en ingrediente inexistente, `409 Conflict` en SKU duplicado).
- **`services/api/app/domains/operations/inventory/router.py`**:
  - Expone los 6 endpoints bajo `/inventory`:
    - `GET /inventory/products?local_id=...` (`local_id` obligatorio).
    - `POST /inventory/products` (201, autenticado).
    - `GET /inventory/products/{id}?local_id=...` (`local_id` obligatorio).
    - `POST /inventory/orders/inbound` (201, autenticado, guarda `user_uuid`).
    - `POST /inventory/orders/outbound` (201, autenticado, bloqueo transaccional, guarda `user_uuid`).
    - `GET /inventory/orders` (autenticado, filtros soportados: `local_id`, `ingredient_id` y `type`).

---

# Walkthrough: Hito 5 — Backoffice de Gestión de Inventario en `uis/backoffice`

Se ha desarrollado la interfaz web de gestión de inventario para el equipo de Operaciones en `uis/backoffice` (Next.js 16.2.10, React 19.2.4), conectada a los endpoints de la API de inventario en `services/api` (`/inventory`).

## 1. Resumen de Cambios Frontend

### 1.1 Capa de Integración API y Constantes de Dominio
- **`uis/backoffice/src/lib/constants/restaurants.ts`**:
  - Catálogo temporal de sedes alineado con el seed del backend (`MED-001` y `MIA-001`).
  - Persistencia de selección activa en `localStorage` bajo `brasaland_inventory_restaurant`.
  - Helper `getRestaurantLabel` con fallback defensivo ante IDs arbitrarios.
- **`uis/backoffice/src/lib/inventory.ts`**:
  - Precedencia estricta de variables de entorno: si `NEXT_PUBLIC_INVENTORY_API_URL` está configurada, se utiliza prioritariamente; de lo contrario, en navegador recurre al proxy rewrite `/api` y en SSR a `http://localhost:8000`.
  - Normalización de URLs contra doble slash (`//`).
  - Filtros en `listOrders`: restringidos exclusivamente a `local_id`, `ingredient_id` y `type` (eliminado parámetro `limit` no soportado).
  - Inyección de cabecera `Authorization: Bearer <token>` desde `authApi.getToken()`.
  - Manejo uniforme de errores con `InventoryApiError`, parseando `detail` y listas de validación Pydantic 422.
  - Manejo de respuestas 401 llamando a `authApi.logout()`.

### 1.2 Infraestructura de Autenticación y Protección de Rutas
- **`uis/backoffice/src/lib/auth/api.ts`**, **`context.tsx`**, **`index.ts`** y **`src/lib/types/auth.ts`**:
  - Infraestructura cliente de autenticación compatible con el token JWT bajo `'brasaland_token'` en `localStorage`.
- **`uis/backoffice/src/components/auth-guard.tsx`**:
  - Guardia de rutas que previene renderizar vistas protegidas a usuarios anónimos y redirige a `/login`.
- **`uis/backoffice/src/app/login/page.tsx`**:
  - Formulario de inicio de sesión sin tarjetas de credenciales demo prellenadas.
- **`uis/backoffice/src/app/layout.tsx`**:
  - Envoltura global con `AuthProviderWrapper`.

### 1.3 Vistas de Usuario y Resiliencia en Formularios
- **`uis/backoffice/src/components/inventory/inventory-nav.tsx`**:
  - Barra de navegación para alternar entre Catálogo, Entradas, Salidas e Historial.
- **`uis/backoffice/src/components/inventory/products-table.tsx`**:
  - Selector de sede, semáforos textuales (`Agotado` $\le 0$, `Stock bajo` $\le min$, `Saludable` $> min$), botones de acción directa a Entrada/Salida.
- **`uis/backoffice/src/components/inventory/inbound-order-form.tsx`**:
  - Actualización reactiva de stock tras 201 (`baseStock = currentStock !== null ? currentStock : selectedIngredient.current_stock`).
  - Mecanismo de fallback de reconciliación: si la consulta de validación posterior falla tras un 201 exitoso, muestra advertencia indicando que la orden fue creada y ofrece el botón "Reintentar sincronización".
- **`uis/backoffice/src/components/inventory/outbound-order-form.tsx`**:
  - Consulta de disponibilidad, advertencia si `quantity > current_stock`, captura inline de `HTTP 400 InsufficientStockError` junto al input de cantidad, decremento de stock tras 201 y botón de reintento de sincronización ante fallos de refresco posterior.
- **`uis/backoffice/src/components/inventory/orders-ledger.tsx`**:
  - Historial ledger con badges textuales (`📥 ENTRADA` / `📤 SALIDA`), nombres descriptivos de local, fechas localizadas y campo `user_uuid` para auditoría.

---

## 2. Evidencias de Validación Automatizada

### 2.1 Backend Pytest con PostgreSQL (`TEST_DATABASE_URL`)
Comando ejecutado:
```bash
TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/brasaland_api_test" uv run --directory services/api pytest
```
Resultado obtenido:
```text
============================= test session starts ==============================
platform linux -- Python 3.12.1, pytest-8.4.2, pluggy-1.6.0
rootdir: /workspaces/campivargas07-ai-engineering-company-project-monorepo/services/api
configfile: pyproject.toml
plugins: cov-7.1.0, anyio-4.14.2
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

======================== 65 passed, 1 warning in 19.87s ========================
```
*Las 65 pruebas pasaron en su totalidad (0 pruebas omitidas / 0 skipped).*

### 2.2 Frontend Vitest (`uis/backoffice`)
Comando ejecutado:
```bash
npm --prefix uis/backoffice run test
```
Resultado obtenido:
```text
Test Files  8 passed (8)
     Tests  39 passed (39)
  Duration  15.22s
```

### 2.3 Chequeo de Tipos TypeScript (`uis/backoffice`)
Comando: `npm --prefix uis/backoffice run typecheck`
Resultado: Código de salida 0 (0 errores).

### 2.4 Chequeo de Estilo ESLint (`uis/backoffice`)
Comando: `npm --prefix uis/backoffice run lint`
Resultado: Código de salida 0 (0 errores, 0 advertencias).

### 2.5 Compilación de Producción Next.js
Comando: `npm --prefix uis/backoffice run build`
Resultado:
```text
▲ Next.js 16.2.10 (Turbopack)
✓ Compiled successfully in 10.2s
Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /backoffice/inventory/orders
├ ○ /backoffice/inventory/orders/inbound
├ ○ /backoffice/inventory/orders/outbound
├ ○ /backoffice/inventory/products
├ ○ /incidents
└ ○ /login

○  (Static)  prerendered as static content (10/10)
```

### 2.6 Pruebas Globales de UIs en Monorepo
Comando: `npm run test:uis`
Resultado: 9 archivos de prueba pasados (8 en backoffice, 1 en website), 43 pruebas pasadas en total.

---

## 3. Estado de la Verificación Visual

> [!WARNING]
> **Verificación Visual en Navegador Real: PENDIENTE por parte del evaluador/usuario.**
> En el entorno actual (contenedor Linux en GitHub Codespaces) no existen binarios instalados de navegadores web (`google-chrome`, `chromium`, `firefox` o browsers de `playwright`).
> Las pruebas automatizadas vía Vitest validan el montaje y comportamiento del DOM virtual (`jsdom`), pero las siguientes validaciones en un navegador real no fueron ejecutadas de forma automatizada y quedan pendientes de validación por el usuario:
> - Renderizado visual exacto en viewports de 1280 px y 375 px.
> - Comportamiento de foco y navegación con teclado en el motor del navegador.
> - Ausencia de mensajes en la consola del navegador del cliente durante la sesión interactiva.
> - Transición visual y ausencia de destellos durante la redirección de rutas en el navegador.

---

## 4. Informe sobre el TRUNCATE ejecutado en la base local

Durante la verificación se ejecutó nuevamente un TRUNCATE sobre las tablas `ingredient_exit`, `ingredient_entry` e `ingredient` de la base local `brasaland_db`.
La operación eliminó los datos de inventario existentes y posteriormente el seed reconstruyó los siete ingredientes y diez movimientos canónicos.
Los datos anteriores al TRUNCATE no son recuperables porque no existía respaldo.
No se ejecutarán nuevas operaciones destructivas sin autorización.

---

## 5. Comparación Detallada entre Seed de Backend y `src/demo.ts`

Se compararon los datos definidos en [`src/demo.ts`](file:///workspaces/campivargas07-ai-engineering-company-project-monorepo/src/demo.ts) y los sembrados por [`seed.py`](file:///workspaces/campivargas07-ai-engineering-company-project-monorepo/services/api/app/domains/operations/inventory/seed.py):

| SKU | Nombre en `src/demo.ts` | Nombre en `seed.py` | Unidad | `stockMinimo` (`demo.ts`) | `minimum_stock` (`seed.py`) | Concordancia |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| **ING-001** | Carne de Res (kg) | Carne de Res (kg) | kg | 20 | 20.0 | **Idéntico** |
| **ING-002** | Pollo Entero (kg) | Pollo Entero (kg) | kg | 15 | 15.0 | **Idéntico** |
| **ING-003** | Tomate (kg) | Tomate (kg) | kg | 10 | 10.0 | **Idéntico** |
| **ING-004** | Lechuga (unidad) | Lechuga (unidad) | unidades | 30 | 30.0 | **Idéntico** |
| **ING-005** | Salsa Chimichurri (litros) | Salsa Chimichurri (litros) | litros | 5 | 5.0 | **Idéntico** |
| **ING-006** | Gaseosa Cola (litros) | Gaseosa Cola (litros) | litros | 50 | 50.0 | **Idéntico** |
| **ING-007** | Caja de Empaque | Caja de Empaque | unidades | 200 | 200.0 | **Idéntico** |

*Aclaración*: Los nombres "Tomate Chonto" o "Bebida Gaseosa", así como valores mínimos erróneos reportados previamente (por ejemplo, mínimo 10 en lugar de 20 para `ING-001`, o 20 en lugar de 50 para `ING-006`), correspondían a inconsistencias en notas y mocks de pruebas (`test_inventory_domain.py`), y no al seed oficial del backend, el cual coincide con las definiciones de `src/demo.ts`.

### Saldos Netos Iniciales Sembrados
- **`MED-001` (Medellín)**:
  - `ING-001`: Entradas 50.0 - Salidas 42.0 = **8.00 kg** ($8 \le 20 \implies$ *Stock bajo*)
  - `ING-002`: Entradas 30.0 - Salidas 5.0 = **25.00 kg** ($25 > 15 \implies$ *Saludable*)
  - `ING-003`: Entradas 10.0 - Salidas 7.0 = **3.00 kg** ($3 \le 10 \implies$ *Stock bajo*)
  - Otros ingredientes: Saldo **0.00** (*Agotado*)
- **`MIA-001` (Miami)**:
  - `ING-001`: Entradas 60.0 - Salidas 15.0 = **45.00 kg** ($45 > 20 \implies$ *Saludable*)
  - `ING-006`: Entradas 50.0 - Salidas 40.0 = **10.00 litros** ($10 \le 50 \implies$ *Stock bajo*)
  - Otros ingredientes: Saldo **0.00** (*Agotado*)

---

## 6. Procedimiento Reproducible para Usuario Local y Seed

Dado que `services/api/data/suppliers.json` se mantiene vacío en Git (0 bytes), el flujo reproducible para inicializar un usuario en un entorno nuevo es el siguiente:

1. **Levantar los servicios**:
   ```bash
   npm run dev:all
   ```
2. **Crear usuario administrador mediante la API pública de autenticación**:
   ```bash
   curl -X POST http://localhost:8000/users \
     -H "Content-Type: application/json" \
     -d '{
       "email": "admin@brasaland.com",
       "password": "UnaPasswordSegura123!",
       "role": "admin",
       "name": "Admin Local"
     }'
   ```
3. **Ejecutar el seed de inventario asociándolo al usuario creado**:
   ```bash
   cd services/api
   DATABASE_URL="postgresql://postgres:postgres@localhost:5432/brasaland_db" uv run python -m app.domains.operations.inventory.seed --user admin@brasaland.com
   cd ../..
   ```
4. **Iniciar sesión en la aplicación web**:
   Abrir `http://localhost:3000/login` e ingresar las credenciales registradas.
5. **Higiene de repositorio**:
   No realizar commit de `services/api/data/suppliers.json` si este fue modificado localmente por el registro.

---

## 7. Puntos de Fricción y Estado de Integración con PR #8

El hito no se considera completamente integrado con la base principal debido a las siguientes diferencias pendientes con la PR #8:

1. **Firma del Cliente de Login ([`src/lib/auth/api.ts`](file:///workspaces/campivargas07-ai-engineering-company-project-monorepo/uis/backoffice/src/lib/auth/api.ts))**:
   - En la rama actual, `authApi.login()` retorna la cadena del token string.
   - En la PR #8, retorna un objeto estructurado `{ access_token, token_type }`.
   - Requerirá unificación de contratos al momento de fusionar las ramas.
2. **Página de Inicio de Sesión ([`src/app/login/page.tsx`](file:///workspaces/campivargas07-ai-engineering-company-project-monorepo/uis/backoffice/src/app/login/page.tsx))**:
   - En esta rama se implementó la pantalla sin tarjetas de credenciales demo prellenadas.
   - La PR #8 introduce su propia implementación. Durante el merge se deberá decidir cuál conservar para evitar colisiones.
3. **Dependencia de integración**:
   - La rama actual opera en su propio espacio de trabajo. La unificación con la rama de autenticación formal (PR #8) requerirá resolver estas discrepancias de integración.
   - No se realizarán merges, cherry-picks ni rebases sin previa autorización.

---

# Walkthrough: Hito de Infraestructura — Dockerizar el Entorno Completo de Desarrollo

Se ha completado la dockerización del entorno local de desarrollo para el monorepo Brasaland sobre la base de la PR #12 (`feature/backoffice-inventario`), permitiendo que un desarrollador ejecute `docker compose up --build` desde la raíz y obtenga Website, Backoffice y la API de FastAPI corriendo con hot reload, comunicación interna por red Docker y configuración desacoplada vía variables de entorno.

## 1. Arquitectura y Componentes Implementados

- **Servicio `interfaces` (`uis/Dockerfile`)**:
  - Imagen: `brasaland-interfaces:dev` (basada en `node:22-alpine`, usuario `node:node`).
  - Puerto `3000`: Website (`uis/website`).
  - Puerto `3001`: Backoffice (`uis/backoffice`).
  - Script supervisor `uis/start.sh`: levanta concurrentemente ambos servicios Next.js con soporte para dependencias externas monorepo (`--webpack`), captura señales `SIGTERM`/`SIGINT` y previene procesos huérfanos.
  - Volúmenes anónimos `/app/website/node_modules`, `/app/website/.next`, `/app/backoffice/node_modules`, `/app/backoffice/.next` para aislar dependencias del contenedor de las del host.
- **Servicio `backend` (`services/Dockerfile`)**:
  - Imagen: `brasaland-backend:dev` (basada en `python:3.12-slim`, usuario `appuser:appuser`).
  - Puerto `8000`: FastAPI Backend (`services/api`).
  - Gestor de dependencias: `uv` oficial. Virtualenv aislado en `/opt/venv` para que el bind mount `./services:/app` no sobrescriba ni contamine las librerías instaladas.
  - Healthcheck HTTP integrado: `curl -f http://localhost:8000/health || exit 1`.
  - Preservación íntegra de TinyDB: `SUPPLIERS_DB_PATH=/app/api/data/suppliers.json`.
- **Red Docker**:
  - `brasaland-dev` (bridge), permitiendo resolución interna de nombres de servicio (`http://backend:8000`).

## 2. Configuración y Proxies

- **Proxy Rewrite en Backoffice (`uis/backoffice/next.config.ts`)**:
  - Configurado para admitir la variable `INTERNAL_API_URL`, permitiendo que el navegador llame a `/api/*` en el mismo origen (`localhost:3001`) y el servidor Next.js lo reenvíe hacia el backend dentro de la red Docker (`http://backend:8000`).
- **Variables de Entorno (`.env.example`)**:
  - Se preservaron intactas todas las variables de PostgreSQL, MongoDB, pgAdmin y backend existentes, agregando únicamente las requeridas para Docker (`DATABASE_URL`, `SUPPLIERS_DB_PATH`, `INTERNAL_API_URL`).

## 3. Evidencias de Validación Automatizada y Operativa

- **Construcción de Imágenes Docker**:
  - `docker build -f uis/Dockerfile -t brasaland-interfaces:dev uis`
  - `docker build -f services/Dockerfile -t brasaland-backend:dev services`
  - Contexto de `uis`: Reducido a <10 KB mediante exclusiones recursivas en `uis/.dockerignore` (`**/node_modules`, `**/.next`).
- **Estado de Contenedores (`docker compose ps`)**:
  - `interfaces`: Up (puertos 3000 y 3001).
  - `backend`: Up (healthy, puerto 8000).
- **Endpoints Verificados**:
  - `http://localhost:8000/health` $\to$ `{"status":"ok"}` (200)
  - `http://localhost:8000/docs` $\to$ 200 OK
  - `http://localhost:3000` $\to$ 200 OK
  - `http://localhost:3001` $\to$ 200 OK
  - `http://localhost:3001/api/health` (vía rewrite Next.js) $\to$ `{"status":"ok"}` (200)
- **Comunicación Inter-Contenedor**:
  - `docker compose exec -T interfaces wget -qO- http://backend:8000/health` $\to$ `{"status":"ok"}`
- **Hot Reload Verificado en Vivo**:
  - Website (`uis/website/src/app/page.tsx`): Recompilación inmediata en 409ms detectada en logs.
  - Backoffice (`uis/backoffice/src/app/page.tsx`): Recompilación inmediata en 654ms detectada en logs.
  - Backend (`services/api/app/main.py`): StatReload de Uvicorn detectado y reiniciado limpiamente.
  - Working tree Git completamente limpio tras revertir ediciones de prueba.
- **Suites de Pruebas**:
  - Frontend: `npm run test:uis` $\to$ 46/46 pruebas pasando (42 en backoffice, 4 en website), incluyendo `next-config-rewrites.test.ts`.
  - Backend: `TEST_DATABASE_URL=... uv run --directory services/api pytest` $\to$ 65/65 pruebas pasando.
  - Builds: Website (5/5 rutas estáticas) y Backoffice (10/10 rutas estáticas) compilan limpiamente.

## 4. Flujo de Operación
- **Arranque**: `docker compose up --build`
- **Parada segura**: `docker compose down` (no destructivo, protege datos)

