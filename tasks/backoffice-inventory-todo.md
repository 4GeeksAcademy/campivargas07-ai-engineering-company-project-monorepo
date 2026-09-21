# Checklist de Tareas — Hito 5: Backoffice de Gestión de Inventario

## Fase 0: Prerrequisitos y Saneamiento del Entorno
- [x] **Tarea 0.1: Integrar/Alinear Autenticación Frontend en `uis/backoffice`**
  - **Acción**: Adoptar infraestructura compatible con PR #8 (`src/lib/auth/api.ts`, `src/lib/auth/context.tsx`, `src/app/login/page.tsx`, `src/components/auth-provider.tsx`, `src/components/auth-guard.tsx`).
  - **Criterio de Aceptación**: Token JWT consistente bajo `'brasaland_token'` en `localStorage`, protección estricta en `AuthGuard` sin destellos de contenido desprotegido. Sin credenciales hardcodeadas en la vista de login.
- [x] **Tarea 0.2: Corregir Error TypeScript y Accesibilidad Preexistente en Pruebas**
  - **Acción**: En `uis/backoffice/src/test/incidents-analyzer.test.tsx:52`, sustituido selector DOM directo por consulta accesible `screen.getByLabelText(/Arrastra el archivo aquí o selecciónalo desde tu equipo/i)`.
  - **Criterio de Aceptación**: El archivo pasa la revisión de tipos y pruebas con accesibilidad WCAG.
- [x] **Tarea 0.3: Limpiar Caché de Next.js y Validar Typecheck Inicial**
  - **Acción**: Limpiar cachés y ejecutar `npm --prefix uis/backoffice run typecheck`.
  - **Criterio de Aceptación**: `typecheck` finaliza con código de salida 0.

---

## Fase 1: Capa de Integración API y Constantes de Dominio
- [x] **Tarea 1.1: Catálogo Canónico Temporal de Locales**
  - **Archivo**: `uis/backoffice/src/lib/constants/restaurants.ts`
  - **Acción**: Restringir `RESTAURANT_LOCATIONS` a las sedes activas con datos sembrados en el backend (`MED-001` y `MIA-001`), documentando que es configuración temporal a reemplazar por un endpoint oficial.
  - **Criterio de Aceptación**: Constante tipada, helper `getRestaurantLabel` con fallback seguro para IDs arbitrarios.
- [x] **Tarea 1.2: Implementar y Normalizar Cliente API Centralizado**
  - **Archivo**: `uis/backoffice/src/lib/inventory.ts`
  - **Acción**:
    - Priorizar `NEXT_PUBLIC_INVENTORY_API_URL` si está configurado en el entorno; si no, en browser usar `/api` (rewrite proxy local) y en SSR `http://localhost:8000`.
    - Normalización estricta de URLs para evitar doble slash (`//`).
    - Uso consistente de `URLSearchParams` soportando exclusivamente `local_id`, `ingredient_id` y `type` (sin parámetro no soportado `limit`).
    - Inyección de cabecera `Authorization: Bearer <token>` mediante `authApi.getToken()`.
    - Implementar `listProducts`, `getProduct`, `createProduct`, `createInboundOrder`, `createOutboundOrder`, `listOrders`.
    - Preservar `status` y `detail` en `InventoryApiError`.
    - Parseo seguro de respuestas no-JSON (502/HTML).
    - Manejo amigable de arrays de validación 422 de Pydantic.
    - Manejo de 401 llamando a `authApi.logout()` sin manipular tokens directamente en el cliente HTTP.
  - **Criterio de Aceptación**: Sin logs de tokens en consola ni manipulación descontrolada de sesión.
- [x] **Tarea 1.3: Suite de Pruebas Unitarias del Cliente de Inventario**
  - **Archivo**: `uis/backoffice/src/test/inventory-api.test.ts`
  - **Acción**: Probar métodos HTTP, inyección de token, 400 (detalle exacto), 401 (logout), respuestas no-JSON (502), validaciones 422, y precedencia de `NEXT_PUBLIC_INVENTORY_API_URL`.
  - **Criterio de Aceptación**: 11 pruebas pasando (100% verdes).

---

## Fase 2: Vista de Productos y Monitoreo de Stock
- [x] **Tarea 2.1: Componente de Navegación del Módulo de Inventario**
  - **Archivo**: `uis/backoffice/src/components/inventory/inventory-nav.tsx`
  - **Acción**: Barra de pestañas accesible con enlaces a `/backoffice/inventory/products`, `/backoffice/inventory/orders/inbound`, `/backoffice/inventory/orders/outbound`, y `/backoffice/inventory/orders`.
  - **Criterio de Aceptación**: Resalta visualmente la pestaña activa según la ruta actual.
- [x] **Tarea 2.2: Implementar Componente de Tabla y Filtros de Productos**
  - **Archivo**: `uis/backoffice/src/components/inventory/products-table.tsx`
  - **Acción**:
    - Selector de sede persistente en `localStorage`.
    - Tabla con SKU, Ingrediente, Categoría, Stock Mínimo, Stock Actual, Estado y Acciones.
    - Semáforos textuales normalizados y accesibles: `Agotado` ($\le 0$), `Stock bajo` ($\le min$), `Saludable` ($> min$).
    - Botones de acción "+ Entrada" y "- Salida" preseleccionando sede e ingrediente.
    - Manejo completo de estados: carga accesible, error con reintento, y estado vacío con CTA para registrar primera entrada.
  - **Criterio de Aceptación**: Sin edición directa de valores de stock; accesibilidad WCAG.
- [x] **Tarea 2.3: Implementar Página Protegida de Productos**
  - **Archivo**: `uis/backoffice/src/app/backoffice/inventory/products/page.tsx`
  - **Acción**: Ensamblar vista bajo guardia de autenticación sin flash de contenido.
  - **Criterio de Aceptación**: Redirige a `/login` si no hay sesión activa.
- [x] **Tarea 2.4: Pruebas de Integración de Productos**
  - **Archivo**: `uis/backoffice/src/test/inventory-products.test.tsx`
  - **Acción**: Probar render de productos, cambio de restaurante, semáforos textuales y estado vacío con CTA.
  - **Criterio de Aceptación**: 3 pruebas pasando al 100%.

---

## Fase 3: Formularios de Entrada y Salida
- [x] **Tarea 3.1: Implementar Formulario de Entrada de Stock (`/inbound`)**
  - **Archivos**:
    - `uis/backoffice/src/components/inventory/inbound-order-form.tsx`
    - `uis/backoffice/src/app/backoffice/inventory/orders/inbound/page.tsx`
  - **Acción**:
    - Selector desplegable mostrando `${name} (SKU: ${sku}) — ${unit}` y enviando el UUID `ingredient_id`.
    - Preselección mediante query parameters (`local_id`, `ingredient_id`).
    - Validación cliente `quantity > 0` (rechazo de NaN, $\le 0$).
    - Al éxito (201): incrementar inmediatamente el balance de stock en memoria para feedback instantáneo, limpiar input de cantidad y mostrar notificación con botón de descarte.
    - Manejo de fallback con advertencia y botón de reintento (`reconcileStock`) si la llamada de reconciliación post-creación fallara.
  - **Criterio de Aceptación**: Feedback de stock inmediato y resiliencia ante desincronizaciones de red.
- [x] **Tarea 3.2: Implementar Formulario de Salida de Stock (`/outbound`)**
  - **Archivos**:
    - `uis/backoffice/src/components/inventory/outbound-order-form.tsx`
    - `uis/backoffice/src/app/backoffice/inventory/orders/outbound/page.tsx`
  - **Acción**:
    - Consulta reactiva de stock con estado de carga ("Consultando...") y cancelación de peticiones desfasadas.
    - Validación cliente `quantity > 0`.
    - Advertencia preventiva y deshabilitación de submit si `quantity > current_stock`.
    - Captura de `HTTP 400 Bad Request` mostrando el `detail` exacto del backend inline junto al input de cantidad.
    - Al éxito (201): decrementar inmediatamente el stock disponible en pantalla y limpiar input de cantidad.
    - Manejo de fallback con advertencia y botón de reintento (`reconcileStock`) si la verificación post-orden fallara.
  - **Criterio de Aceptación**: Saldo actualizado en memoria; prevención activa de inconsistencias.
- [x] **Tarea 3.3: Pruebas Automatizadas de Formularios de Órdenes**
  - **Archivo**: `uis/backoffice/src/test/inventory-orders-forms.test.tsx`
  - **Acción**: Verificar incremento dinámico de stock en entrada, validación $\le 0$, advertencia y bloqueo de sobregiro en salida, error 400 inline, decremento dinámico de stock en salida y fallback con botón de reintento ante error de reconciliación.
  - **Criterio de Aceptación**: 7 pruebas pasando al 100%.

---

## Fase 4: Historial de Órdenes
- [x] **Tarea 4.1: Implementar Vista y Página de Historial (`/orders`)**
  - **Archivos**:
    - `uis/backoffice/src/components/inventory/orders-ledger.tsx`
    - `uis/backoffice/src/app/backoffice/inventory/orders/page.tsx`
  - **Acción**:
    - Consumo de `listOrders` para recuperar movimientos inmutables (filtros: `local_id`, `ingredient_id`, `type`).
    - Badges legibles con icono y texto explícito: `📥 ENTRADA` y `📤 SALIDA`.
    - Nombre descriptivo de sede (`getRestaurantLabel`), fecha localizada `DD/MM/YYYY HH:mm` y `user_uuid`.
    - Filtros por local y por tipo (Todos / Entradas / Salidas).
    - Estado vacío con CTAs a "Registrar entrada" y "Registrar salida".
  - **Criterio de Aceptación**: Ordenamiento descendente conservado; vista responsive.
- [x] **Tarea 4.2: Pruebas Automatizadas del Historial**
  - **Archivo**: `uis/backoffice/src/test/inventory-orders-history.test.tsx`
  - **Acción**: Validar badges legibles, nombres de sedes, filtrado reactivo y estado vacío con acciones.
  - **Criterio de Aceptación**: 4 pruebas pasando al 100%.

---

## Fase 5: Integración Global y Verificación Final
- [x] **Tarea 5.1: Actualizar Navegación General en `BackofficeHeader`**
  - **Archivo**: `uis/backoffice/src/components/backoffice-header.tsx`
  - **Acción**: Enlace "Inventario" apuntando a `/backoffice/inventory/products`.
  - **Criterio de Aceptación**: `src/test/backoffice-header.test.tsx` 100% verde con 4 pruebas.
- [x] **Tarea 5.2: Eliminar Rewrite Confuso en `next.config.ts`**
  - **Archivo**: `uis/backoffice/next.config.ts`
  - **Acción**: Proxy limpio `/api/:path* -> http://127.0.0.1:8000/:path*`. Todas las páginas de frontend residen exclusivamente bajo `/backoffice/inventory/*`. Sin CORS regex en backend.
  - **Criterio de Aceptación**: Sin enmascaramiento con los endpoints reales del backend.
- [x] **Tarea 5.3: Limpieza de Base de Datos y Credenciales**
  - **Acción**: `services/api/data/suppliers.json` restaurado a estado limpio original sin usuarios demo ni hashes registrados.
- [x] **Tarea 5.4: Batería Completa de Verificación Automatizada**
  - [x] `TEST_DATABASE_URL=... uv run --directory services/api pytest`: 65 pruebas pasando al 100% (0 omitidas, 0 fallos).
  - [x] `npm --prefix uis/backoffice run test`: 39 pruebas pasando en 8 suites.
  - [x] `npm --prefix uis/backoffice run typecheck`: 0 errores TypeScript.
  - [x] `npm --prefix uis/backoffice run lint`: 0 errores ESLint.
  - [x] `npm --prefix uis/backoffice run build`: build Turbopack exitoso (10/10 rutas estáticas prerenderizadas).
  - [x] `npm run test:uis`: 43 pruebas pasando en todo el monorepo (39 backoffice + 4 website).
- [ ] **Tarea 5.5: Verificación Visual en Navegador Real (PENDIENTE)**
  - Estado: Pendiente de inspección manual por parte del usuario en su navegador web (entorno sin binarios de navegador para automatización).
  - [ ] Login y logout.
  - [ ] Protección de las cuatro rutas.
  - [ ] Productos en MED-001 y MIA-001.
  - [ ] Entrada y salida.
  - [ ] Actualización del stock.
  - [ ] Error 400 inline.
  - [ ] Historial.
  - [ ] Vista móvil.
  - [ ] Navegación por teclado.
  - [ ] Consola del navegador.


