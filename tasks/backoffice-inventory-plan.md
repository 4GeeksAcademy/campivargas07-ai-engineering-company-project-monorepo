# Plan de Implementación — Hito 5: Backoffice de Gestión de Inventario

## 1. Objetivo y Alcance

### 1.1 Objetivo General
Desarrollar e integrar la interfaz de gestión de inventario para el equipo de Operaciones dentro de la aplicación existente `uis/backoffice` (Next.js 16.2.10, React 19.2.4, TypeScript 5). La interfaz consumirá datos en tiempo real de la API de inventario en `services/api` (`/inventory`), garantizando consistencia transaccional, autenticación JWT, visualización reactiva de stock, manejo inline de errores y trazabilidad de movimientos.

### 1.2 Páginas y Vistas Protegidas
1. **`/backoffice/inventory/products`**: Catálogo de ingredientes, selector de sede/restaurante (`local_id`), visualización de `current_stock`, semáforo de estado de stock frente a `minimum_stock` (sin números mágicos), y acciones directas para iniciar órdenes de entrada o salida.
2. **`/backoffice/inventory/orders/inbound`**: Formulario de recepción/entrada de stock (`POST /inventory/orders/inbound`), selector de ingrediente (nombre/SKU, sin exponer UUIDs al usuario), selección de restaurante, cantidad y confirmación visual.
3. **`/backoffice/inventory/orders/outbound`**: Formulario de consumo/salida de stock (`POST /inventory/orders/outbound`), consulta reactiva del stock actual antes del envío, alerta preventiva si la cantidad supera el disponible, control de concurrencia y manejo del error `HTTP 400 InsufficientStockError`.
4. **`/backoffice/inventory/orders`**: Historial de movimientos (`GET /inventory/orders`), vista tabular de solo lectura con diferenciación gráfica entre entradas y salidas, ordenamiento determinista descendente por fecha, y metadata (`sku`, `nombre`, `local_id`, `cantidad`, `fecha`, `user_uuid`).

### 1.3 Principios Arquitectónicos y Restricciones
- **Separación de capas**: Ningún componente o página llamará a `fetch` directamente; todas las operaciones pasarán por `uis/backoffice/src/lib/inventory.ts`.
- **Autenticación unificada**: Reutilización estricta del token JWT almacenado en `localStorage` bajo la clave `'brasaland_token'`.
- **Sin mocks en producción**: Todos los datos se obtienen del backend real (`services/api`).
- **Stock no editable**: El stock es estrictamente derivado (`current_stock = SUM(inbound) - SUM(outbound)` en backend). La UI no ofrece edición directa de stock.
- **Next.js moderno**: Páginas como Server Components para metadata y esqueleto; vistas interactivas como Client Components (`'use client'`).

---

## 2. Estado Confirmado del Repositorio y PR #11

### 2.1 Inspección de la PR #11
- **Rama origen de backend**: `feature/db-inventario` (PR #11).
- **Rama de trabajo frontend**: `feature/backoffice-inventario`.
- **Commit base**: `5bbdbbf` (*"Implementar la integración con PostgreSQL y pruebas de concurrencia"*).
- **Backend adoptado**: `services/api/app/domains/operations/inventory/` (FastAPI + SQLModel + PostgreSQL).
- **Endpoints verificados en el router**:
  - `GET /inventory/products?local_id=...` (requiere `Authorization: Bearer <token>`, `local_id` obligatorio $\to 422$ si falta).
  - `POST /inventory/products` (requiere autenticación, 201 Created).
  - `GET /inventory/products/{product_id}?local_id=...` (requiere autenticación y `local_id`).
  - `POST /inventory/orders/inbound` (requiere autenticación, 201 Created, extrae `user_uuid` desde `current_user`).
  - `POST /inventory/orders/outbound` (requiere autenticación, bloqueo pesimista `SELECT ... FOR UPDATE`, 201 Created, `HTTP 400` ante saldo insuficiente).
  - `GET /inventory/orders` (requiere autenticación, filtros opcionales `local_id`, `ingredient_id`, `type`).
- **Backend desestimado**: El router alternativo en `services/backend` con prefijo `/api/v1/inventario` no se utilizará.
- **Datos semilla verificados (`seed.py`)**:
  - Ingredientes sembrados: `ING-001` a `ING-007` (coincidentes con `src/demo.ts`).
  - Locales con stock sembrado: `MED-001` (Medellín - El Poblado) y `MIA-001` (Miami Downtown).
  - Requiere un usuario previamente creado en TinyDB (`--user <email|uuid|doc_id>`).

---

## 3. Contratos de API y Manejo de Errores

### 3.1 DTOs y Esquemas de Petición / Respuesta

#### A. Ingrediente con Stock (`IngredientWithStockResponse`)
```typescript
export interface IngredientWithStock {
  id: string; // UUID
  sku: string;
  name: string;
  category: 'carne' | 'verdura' | 'salsa' | 'bebida' | 'empaque' | 'limpieza';
  unit_of_measure: string;
  minimum_stock: number;
  perishable: boolean;
  created_at: string; // ISO 8601
  local_id: string;
  current_stock: number;
}
```

#### B. Registro de Orden Inbound / Outbound
```typescript
export interface InboundOrderCreate {
  ingredient_id: string; // UUID
  local_id: string;      // e.g. "MED-001"
  quantity: number;      // > 0
}

export interface OutboundOrderCreate {
  ingredient_id: string; // UUID
  local_id: string;      // e.g. "MED-001"
  quantity: number;      // > 0
}
```

#### C. Respuesta de Orden (`OrderResponse`)
```typescript
export interface InventoryOrder {
  id: string; // UUID
  type: 'inbound' | 'outbound';
  ingredient_id: string; // UUID
  ingredient_sku: string;
  ingredient_name: string;
  local_id: string;
  quantity: number;
  user_uuid: string; // UUID
  created_at: string; // ISO 8601
}

export interface OrderListResponse {
  orders: InventoryOrder[];
  total: number;
}
```

### 3.2 Formato de Errores del Backend y Estrategia de Parseo
FastAPI retorna los errores en dos formatos principales:
1. **Errores de Negocio (`HTTPException` - 400, 401, 403, 404, 409)**:
   ```json
   { "detail": "Insufficient stock for ingredient 'Carne de Res (kg)' (SKU: ING-001) in restaurant 'MED-001'. Available: 8.0, requested: 100.0" }
   ```
2. **Errores de Validación Pydantic (`HTTP 422 Unprocessable Entity`)**:
   ```json
   {
     "detail": [
       { "loc": ["body", "quantity"], "msg": "Input should be greater than 0", "type": "greater_than" }
     ]
   }
   ```
3. **Mapeo en `inventory.ts`**:
   - Si `detail` es `string`: se expone directamente al usuario.
   - Si `detail` es `array`: se concatenan los mensajes (`err.msg`).
   - Si `status === 401`: se limpia `brasaland_token` de `localStorage` y se redirige a `/login`.
   - Excepción tipada: `InventoryApiError` (`message`, `status`, `detail`).

---

## 4. Decisiones de Arquitectura y UI

### 4.1 Selección de Restaurante (`local_id`)
- **Problema**: El backend no dispone de un endpoint `GET /locales` o `GET /locations`.
- **Decisión**:
  - Se define un catálogo canónico frontend en `uis/backoffice/src/lib/constants/restaurants.ts` alineado con `src/demo.ts` y el seed del backend:
    - `MED-001`: *"Brasaland El Poblado (Medellín, CO)"* (Sede principal con stock inicial).
    - `MIA-001`: *"Brasaland Miami Downtown (Miami, USA)"* (Sede USA con stock inicial).
    - `MED-002`: *"Brasaland Centro (Medellín, CO)"*.
    - `BOG-001`: *"Brasaland Chapinero (Bogotá, CO)"*.
    - `ORL-001`: *"Brasaland Orlando (Orlando, USA)"*.
  - Sede por defecto: `MED-001`.
  - Persistencia de selección: Se almacena la sede seleccionada en `localStorage` (`brasaland_current_restaurant`) para que persista al navegar entre las cuatro vistas.
  - Comunicación entre vistas: Al hacer clic en "Registrar Entrada" o "Registrar Salida" desde la tabla de productos, se navega mediante query parameters:
    `/backoffice/inventory/orders/inbound?local_id=MED-001&ingredient_id=<uuid>`

### 4.2 Indicadores Visuales de Stock (Semáforo Dinámico)
Para evitar números mágicos, el estado del stock se calcula exclusivamente comparando `current_stock` contra `minimum_stock`:
- **Agotado (Rojo)**: `current_stock <= 0` (Badge: *"Agotado"* / `chip-danger`).
- **Stock Bajo (Amarillo/Naranja)**: `0 < current_stock <= minimum_stock` (Badge: *"Stock Bajo"* / `chip-warn`).
- **Stock Saludable (Verde)**: `current_stock > minimum_stock` (Badge: *"Saludable"* / `chip-ok`).

### 4.3 Consulta Reactiva en Formulario de Salida
- Al cambiar el ingrediente o el restaurante en `/orders/outbound`, se dispara una consulta inmediata a `GET /inventory/products/{id}?local_id=...` para conocer el saldo disponible en tiempo real.
- Si el usuario ingresa una cantidad superior al disponible, se muestra una alerta visual preventiva:
  > *⚠️ Advertencia: La cantidad solicitada (X) supera el stock disponible actual (Y). El servidor rechazará la operación.*
- El servidor mantiene la autoridad final mediante bloqueo pesimista `SELECT ... FOR UPDATE`. Si concurre una salida simultánea y el backend responde `400 Bad Request`, el mensaje de error exacto del servidor se muestra inline junto al formulario y los campos permanecen intactos para que el operador pueda corregir la cantidad.

### 4.4 Navegación e Integración de Cabecera
- Se actualiza `uis/backoffice/src/components/backoffice-header.tsx` para incluir el enlace a `Inventario` en la barra de navegación principal.
- Se implementa una barra de pestañas secundaria en las páginas de inventario:
  `[Productos y Stock] | [Registrar Entrada] | [Registrar Salida] | [Historial de Órdenes]`.
- Se mantiene el soporte para rutas directas bajo `/backoffice/inventory/*` y se agregan reescrituras/redirecciones en `next.config.ts` desde `/inventory/*` para evitar errores 404 por variación de prefijo.

---

## 5. Estrategia de Implementación por Fases (Cortes Verticales)

### Fase 0: Prerrequisitos y Saneamiento del Entorno
- **Tarea 0.1**: Resolver la disponibilidad de autenticación frontend en `uis/backoffice` (incorporar o sincronizar la infraestructura de PR #8: `authApi`, `AuthProvider`, `useAuth`, `/login`, almacenamiento en `brasaland_token`).
- **Tarea 0.2**: Corregir error de tipos en `uis/backoffice/src/test/incidents-analyzer.test.tsx` (reemplazar llamada inválida a `screen.getByLabelElement`).
- **Tarea 0.3**: Limpiar artefactos residuales de `.next/dev/types/` para asegurar que `typecheck` y `lint` pasen al 100%.

### Fase 1: Capa de Integración API (`inventory.ts`) y Constantes
- **Tarea 1.1**: Crear `uis/backoffice/src/lib/constants/restaurants.ts` con la lista de locales canónicos y funciones de apoyo.
- **Tarea 1.2**: Crear `uis/backoffice/src/lib/inventory.ts` con todos los tipos TypeScript y los 6 métodos de API (`listProducts`, `getProduct`, `createProduct`, `createInboundOrder`, `createOutboundOrder`, `listOrders`).
- **Tarea 1.3**: Batería de pruebas unitarias para el cliente en `uis/backoffice/src/test/inventory-api.test.ts` (rutas, headers, bearer token, serialización, manejo de errores 400/401/404/409/422/500).

> **CHECKPOINT 1**: Verificar que `inventory.ts` compila y sus pruebas unitarias pasan con 100% de éxito.

### Fase 2: Vista de Catálogo y Stock (`/backoffice/inventory/products`)
- **Tarea 2.1**: Crear componente de navegación de pestañas de inventario (`InventoryNav`).
- **Tarea 2.2**: Crear vista cliente `ProductsView` con selector de restaurante, tabla de productos, semáforo de stock (`Saludable`, `Bajo`, `Agotado`), estados de carga/error/vacío y botones de acción.
- **Tarea 2.3**: Crear página `uis/backoffice/src/app/backoffice/inventory/products/page.tsx` protegida con verificación de sesión.
- **Tarea 2.4**: Pruebas de integración de la vista en `uis/backoffice/src/test/inventory-products.test.tsx`.

### Fase 3: Formularios de Entrada y Salida (`/inbound` y `/outbound`)
- **Tarea 3.1**: Implementar formulario de entrada en `uis/backoffice/src/app/backoffice/inventory/orders/inbound/page.tsx`:
  - Carga ingredientes disponibles, preselecciona parámetros de URL, envía `POST /inventory/orders/inbound`, muestra éxito y limpia campos.
- **Tarea 3.2**: Implementar formulario de salida en `uis/backoffice/src/app/backoffice/inventory/orders/outbound/page.tsx`:
  - Consulta reactiva de stock, alerta en tiempo real si `quantity > current_stock`, envío a `POST /inventory/orders/outbound`, captura de `HTTP 400` inline sin limpiar el formulario.
- **Tarea 3.3**: Pruebas unitarias e interactivas de ambos formularios en `uis/backoffice/src/test/inventory-orders-forms.test.tsx`.

> **CHECKPOINT 2**: Validar flujo completo de entrada exitosa, salida exitosa y rechazo por stock insuficiente en pruebas de frontend.

### Fase 4: Historial de Órdenes (`/backoffice/inventory/orders`)
- **Tarea 4.1**: Implementar vista de solo lectura en `uis/backoffice/src/app/backoffice/inventory/orders/page.tsx`:
  - Listado de movimientos con badges ("Entrada" en verde, "Salida" en rojo), campos requeridos (`sku`, `nombre`, `cantidad`, `local_id`, `fecha`, `user_uuid`), filtro opcional por local y tipo.
- **Tarea 4.2**: Pruebas de renderizado e interacciones del historial en `uis/backoffice/src/test/inventory-orders-history.test.tsx`.

### Fase 5: Integración Global, Navegación y Verificaciones Finales
- **Tarea 5.1**: Integrar enlaces de inventario en `BackofficeHeader` y actualizar pruebas existentes de la cabecera.
- **Tarea 5.2**: Configurar reescrituras/redirecciones en `next.config.ts` para rutas con y sin prefijo `/backoffice`.
- **Tarea 5.3**: Actualizar `uis/backoffice/.env.example` con `NEXT_PUBLIC_INVENTORY_API_URL=http://localhost:8000`.
- **Tarea 5.4**: Ejecución de la suite completa de calidad (`test`, `typecheck`, `lint`, `build`).

> **CHECKPOINT 3**: Build de producción limpio (`npm run build`) y todas las pruebas verdes en `uis/backoffice`.

---

## 6. Plan de Verificación

### 6.1 Pruebas Automatizadas
Comandos ejecutables desde la raíz del monorepo:
```bash
# Pruebas unitarias y de integración de frontend
npm --prefix uis/backoffice run test

# Validación estricta de tipos TypeScript
npm --prefix uis/backoffice run typecheck

# Verificación de reglas de estilo y buenas prácticas
npm --prefix uis/backoffice run lint

# Compilación de producción en Next.js (Turbopack)
npm --prefix uis/backoffice run build
```

### 6.2 Verificación Manual E2E (Checklist de Aceptación)
1. **Arranque de servicios**:
   - Backend: `DATABASE_URL=postgresql://... uv run uvicorn app.main:app --port 8000`
   - Siembra de datos: `uv run python -m app.domains.operations.inventory.seed --user admin@brasaland.com`
   - Backoffice: `npm --prefix uis/backoffice run dev`
2. **Flujo operativo**:
   - Iniciar sesión en `/login` con credenciales válidas.
   - Navegar a `/backoffice/inventory/products`.
   - Cambiar de restaurante a `MED-001`; verificar que se muestran 7 ingredientes con `current_stock` (p. ej. `Carne de Res` con stock 8 kg y badge *Stock Bajo*).
   - Hacer clic en "Entrada" en `Carne de Res` $\to$ navega a `/backoffice/inventory/orders/inbound` con `MED-001` y `ING-001` preseleccionados.
   - Ingresar cantidad 20 y enviar $\to$ mensaje de éxito visible y formulario reseteado.
   - Regresar a `/backoffice/inventory/products` $\to$ verificar que el stock aumentó a 28 kg y el badge cambió a *Saludable*.
   - Navegar a `/backoffice/inventory/orders/outbound` $\to$ seleccionar `Carne de Res`, observar stock reactivo (28 kg).
   - Intentar registrar salida de 100 kg $\to$ ver alerta preventiva y, al enviar, recibir error legible de backend `HTTP 400` sin perder el valor en el formulario.
   - Registrar salida válida de 5 kg $\to$ mensaje de éxito.
   - Navegar a `/backoffice/inventory/orders` $\to$ constatar la presencia de ambos movimientos en el historial ordenados cronológicamente con su respectivo `user_uuid`.

---

## 7. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
| :--- | :--- | :--- |
| **Falta de backend de locales** | Selección inconsistente o fallos 422 por `local_id` erróneo | Catálogo tipado y validado en `restaurants.ts` alineado con `src/demo.ts` y `seed.py`. |
| **Inconsistencia de Auth Frontend** | Imposibilidad de probar rutas protegidas si PR #8 no está integrada | Sincronizar limpiamente la infraestructura cliente de PR #8 (`brasaland_token`) como Tarea 0.1 sin alterar el backend. |
| **Desincronización de Stock en Salidas Concurridas** | Error 400 inesperado para el usuario final | Advertencia previa reactiva en UI y presentación amigable e inline del `detail` devuelto por el backend. |
| **Rutas relativas vs `/backoffice`** | Errores 404 al navegar entre links | Soporte directo de rutas `/backoffice/inventory/*` y rewrites automáticos en `next.config.ts`. |

---

## 8. Archivos Afectados

### Archivos Nuevos
- `uis/backoffice/src/lib/constants/restaurants.ts`
- `uis/backoffice/src/lib/inventory.ts`
- `uis/backoffice/src/components/inventory/inventory-nav.tsx`
- `uis/backoffice/src/components/inventory/products-table.tsx`
- `uis/backoffice/src/components/inventory/inbound-order-form.tsx`
- `uis/backoffice/src/components/inventory/outbound-order-form.tsx`
- `uis/backoffice/src/components/inventory/orders-ledger.tsx`
- `uis/backoffice/src/app/backoffice/inventory/products/page.tsx`
- `uis/backoffice/src/app/backoffice/inventory/orders/inbound/page.tsx`
- `uis/backoffice/src/app/backoffice/inventory/orders/outbound/page.tsx`
- `uis/backoffice/src/app/backoffice/inventory/orders/page.tsx`
- `uis/backoffice/src/test/inventory-api.test.ts`
- `uis/backoffice/src/test/inventory-products.test.tsx`
- `uis/backoffice/src/test/inventory-orders-forms.test.tsx`
- `uis/backoffice/src/test/inventory-orders-history.test.tsx`

### Archivos a Modificar
- `uis/backoffice/src/components/backoffice-header.tsx` (enlace al módulo de inventario)
- `uis/backoffice/next.config.ts` (soporte de redirección/reescritura para `/inventory`)
- `uis/backoffice/.env.example` (documentar `NEXT_PUBLIC_INVENTORY_API_URL`)
- `uis/backoffice/src/test/incidents-analyzer.test.tsx` (corrección puntual del error TypeScript preexistente)
- `uis/backoffice/src/test/backoffice-header.test.tsx` (actualización de aserciones de navegación)

