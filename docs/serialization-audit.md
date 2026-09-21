# Auditoría de serialización del backend de Brasaland

## Estado de implementación

La implementación se inició en la rama `feature/serialization-audit`. Este documento conserva el diagnóstico inicial y añade el estado de los cambios aplicados. La auditoría ya no está pendiente de implementación; queda pendiente la validación completa en entorno integrado y la revisión final del plan.

## 1. Alcance y evidencia

El alcance implementado es `services/api`, backend activo del hito actual:

- `docker-compose.yml` construye `services/Dockerfile` y expone el backend en `8000`.
- `services/Dockerfile` usa `WORKDIR /app/api` y arranca `app.main:app`.
- `services/api/app/main.py` registra auth, usuarios, perfiles, proveedores, incidencias, inventario y health.
- `uis/backoffice` consume `/auth/*`, `/users`, `/profiles/*`, `/api/incidents/*` e `/inventory/*`.

`services/backend` queda fuera de alcance por ser el backend de inventario de un hito anterior: usa otro punto de entrada, puerto `8001`, MongoDB/PostgreSQL, Alembic y rutas `/api/v1`.

La rama de trabajo se creó como `feature/serialization-audit`. Antes de implementar, el árbol estaba sin cambios locales reportados por `git status --short`.

## 2. Inventario inicial y final

| Método y ruta | Propósito | Consumidor | Entrada | Respuesta inicial / final | Campos necesarios | Campos internos | Estado inicial | Estado tras implementación |
|---|---|---|---|---|---|---|---|---|
| `GET /health` | Healthcheck | Docker/operación | Ninguna | `dict` / `HealthResponse` | `status` | Ninguno | ❌ | ✅ |
| `POST /auth/login` | Login y JWT | `auth/api.ts`, login | `email`, `password` | `TokenResponse` | `access_token`, `token_type` | Password solo entrada | ✅ | ✅ |
| `GET /auth/me` | Sesión y perfil autenticado | `auth/context.tsx` | Bearer | `AuthMeResponse` anidado | Usuario, email propio, perfil | Hash/password | ⚠️ | ✅ con tipos frontend alineados |
| `POST /users` | Registro | Contexto/formulario de auth | Email, password, role y perfil opcional | `UserResponse`, `201` | `id`, email, role, activo, fecha | Password/hash | ✅ | ✅ |
| `GET /users` | Listado de usuarios | Consumidor directo no confirmado | Bearer | `UserListResponse` | Campos de administración y trazabilidad | Hash/password | ⚠️ | ✅, sin hash |
| `GET /users/{user_id}` | Detalle de usuario | No confirmado | Bearer, id | `UserResponse` | Campos de usuario | Hash/password | ⚠️ | ✅ |
| `PUT /users/{user_id}` | Editar email/rol | No confirmado | Email, role | `UserResponse` | Campos controlados por servidor | Password/hash | ✅ | ✅ |
| `DELETE /users/{user_id}` | Borrado de usuario/perfil | No confirmado | Bearer, id | Dict / `DeleteResponse` | `detail` | Entidad eliminada | ❌ | ✅ |
| `GET /profiles/me` | Obtener perfil | Cliente auth/perfil | Bearer | `ProfileResponse` | Perfil propio | Identificador interno, según consumidor | ✅ | ✅ |
| `PUT /profiles/me` | Editar perfil | `auth/api.ts` | Nombre, teléfono, dirección | `ProfileResponse` | Campos escribibles | `id`, `user_id` controlados | ✅ | ✅ |
| `POST /api/suppliers` | Crear proveedor | Consumidor directo no confirmado | Datos del proveedor | `SupplierResponse`, `201` | Datos comerciales, estado | ID y fecha | ✅ | ✅ |
| `GET /api/suppliers` | Listar proveedores | Consumidor directo no confirmado | Filtros país/categoría | `SupplierListResponse` | Datos de tabla | Relaciones no justificadas | ⚠️ | ✅ provisional |
| `GET /api/suppliers/{supplier_id}` | Detalle proveedor | No confirmado | ID | `SupplierResponse` | Datos completos del proveedor | Persistencia no contractual | ✅ | ✅ |
| `PATCH /api/suppliers/{supplier_id}/rate` | Cambiar tarifa | No confirmado | `montoMinimoOrden` | `SupplierResponse` | Tarifa y fecha | Fecha controlada por servidor | ✅ | ✅ |
| `PATCH /api/suppliers/{supplier_id}/status` | Cambiar estado | No confirmado | `status` | `SupplierResponse` | Estado | Campos no escribibles | ✅ | ✅ |
| `DELETE /api/suppliers/{supplier_id}` | Borrar proveedor | No confirmado | Bearer, ID | Dict / `DeleteResponse` | `detail` | Entidad eliminada | ❌ | ✅ |
| `POST /api/incidents/analyze` | Analizar CSV | `incidents-api.ts`, vista de incidencias | Multipart CSV UTF-8 | `IncidentAnalysisResponse` | Métricas y desgloses | Archivo temporal | ✅ | ✅ |
| `GET /api/incidents/results/export` | Exportar resultado | Botón de descarga | Bearer | `Response` CSV | Contenido CSV | No es JSON; no convertir | ⚠️ | ⚠️ contrato HTTP documentado |
| `GET /inventory/products` | Listado de ingredientes con stock | `ProductsTable`, formularios | Query `local_id` | Lista `IngredientWithStockResponse` | Producto, local y stock | Relaciones completas | ✅ | ✅ |
| `POST /inventory/products` | Crear ingrediente | Cliente de inventario | `IngredientCreate` | `IngredientResponse`, `201` | Campos escribibles | ID/fecha | ✅ | ✅ |
| `GET /inventory/products/{product_id}` | Detalle con stock | Cliente inventario | UUID y `local_id` | `IngredientWithStockResponse` | Proyección plana | Relaciones completas | ✅ | ✅ |
| `POST /inventory/orders/inbound` | Registrar entrada | `InboundOrderForm` | Ingrediente, local, cantidad | `OrderResponse`, `201` | Movimiento, `user_uuid`, fecha | Stock calculado | ✅ | ✅ |
| `POST /inventory/orders/outbound` | Registrar salida | `OutboundOrderForm` | Ingrediente, local, cantidad | `OrderResponse`, `201` | Movimiento, `user_uuid`, fecha | Stock calculado | ✅ | ✅ |
| `GET /inventory/orders` | Historial de movimientos | `OrdersLedger` | Filtros local/ingrediente/tipo | `OrderListResponse` | Campos del ledger y `user_uuid` | Relaciones completas | ✅ | ✅ |

## 3. Hallazgos de seguridad

Comprobado en esquemas y servicios:

- `hashed_password` se utiliza para persistencia y verificación, pero no pertenece a `UserResponse` ni `UserOut`.
- El password de registro/login es únicamente de entrada.
- El JWT `access_token` sí forma parte del contrato de login y se conserva.
- `GET /auth/me` puede devolver el email del usuario autenticado.
- `user_uuid` del movimiento se conserva porque `OrdersLedger` lo consume para trazabilidad.

La política de autoasignación de rol en `POST /users` continúa siendo una decisión de producto pendiente: el comportamiento existente permite solicitar `admin` públicamente y no se cambió en esta implementación mínima.

## 4. Cambios implementados

### Backend

- `services/api/app/main.py`
  - Se añadió `HealthResponse`.
  - `GET /health` ahora declara `response_model=HealthResponse`.
- `services/api/app/domains/users/schemas.py`
  - Se añadió `DeleteResponse`.
- `services/api/app/domains/users/router.py`
  - `DELETE /users/{user_id}` declara `response_model=DeleteResponse`.
- `services/api/app/domains/procurement/suppliers/schemas.py`
  - Se añadió `DeleteResponse`.
- `services/api/app/domains/procurement/suppliers/router.py`
  - `DELETE /api/suppliers/{supplier_id}` declara `response_model=DeleteResponse`.

### Frontend

- `uis/backoffice/src/lib/types/auth.ts`
  - Se alineó `AuthMeResponse` con la respuesta backend anidada `{ user, profile }`.
  - Se conservaron los campos de trazabilidad `uuid` y `created_at`.

### Pruebas

- `services/api/tests/test_serialization_contracts.py`
  - Health JSON y media type.
  - Ausencia de `password` y `hashed_password` en listados de usuarios.
  - Contrato explícito de borrado de usuario.
  - Presencia de contratos en OpenAPI.

## 5. Contratos especiales

### `GET /health`

- HTTP `200`.
- `Content-Type: application/json`.
- Cuerpo: `{ "status": "ok" }`.
- Modelo OpenAPI: `HealthResponse`.

### `DELETE /users/{user_id}` y `DELETE /api/suppliers/{supplier_id}`

- Mantienen el comportamiento HTTP existente (`200` con cuerpo JSON), para evitar una ruptura innecesaria con consumidores.
- Cuerpo con forma `{ "detail": "..." }`.
- Modelo OpenAPI: `DeleteResponse`.
- Los errores `403` y `404` siguen siendo respuestas de error FastAPI.

### `GET /api/incidents/results/export`

- No se convierte a JSON.
- HTTP `200` cuando existe un análisis.
- `Content-Type: text/csv; charset=utf-8`.
- `Content-Disposition: attachment; filename="results.csv"`.
- HTTP `404` cuando no existe un resultado previo.
- Su contrato es de archivo, no de objeto JSON serializado.

## 6. Compatibilidad y riesgos

- Se evitó cambiar códigos de estado de borrado.
- Se evitó eliminar timestamps, UUIDs o `user_uuid` usados para trazabilidad.
- El cambio de `AuthMeResponse` en TypeScript corrige una discrepancia existente; debe validarse con pruebas de UI.
- No se alteró `services/backend`.
- No se modificaron `CONTEXT.md`, `company-choice.md`, `projectbrief.md`, `techContext.md`, `infra/` ni `mcps/`.
- La exportación CSV mantiene su formato y cabeceras.

## 7. Validaciones pendientes

Pendiente de ejecutar tras esta implementación:

```bash
uv run --directory services/api pytest
npm --prefix uis/backoffice run test
npm --prefix uis/backoffice run typecheck
npm --prefix uis/backoffice run lint
```

También queda pendiente validar manualmente al menos tres endpoints mediante `/docs`, incluyendo health, login y un endpoint de inventario o incidencias.

La implementación se considera funcionalmente aplicada, pero la entrega no se considera cerrada hasta completar estas validaciones.
