# Plan de Telemetría de Brasaland
## Arquitectura de Datos, Observabilidad y Producto para Operaciones Multi-Sede

---

## 1. Resumen Ejecutivo

Brasaland es una cadena de restaurantes a la brasa fundada en 2008 en Medellín, Colombia, que actualmente opera 14 locales propios distribuidos en dos mercados internacionales: **Colombia** (operando en pesos colombianos, COP) y **Estados Unidos - Florida** (operando en dólares estadounidenses, USD). La organización genera aproximadamente \$6 millones de dólares en ingresos anuales y cuenta con una plantilla de ~115 colaboradores.

Históricamente, la operación se ha gestionado mediante herramientas fragmentadas diseñadas para un único local: pedidos de insumos coordinados por WhatsApp y llamadas telefónicas, reportes de turnos en hojas de cálculo y papel, tarjetas físicas de fidelización ("Brasa Points") y terminales de punto de venta (POS) heterogéneos sin integración centralizada. Esta falta de visibilidad en tiempo real genera sobrestock y desperdicio en algunas sedes mientras otras sufren quiebres de inventario de ingredientes críticos durante los turnos pico de servicio (e.g. 7:00 PM).

El presente **Plan de Telemetría de Brasaland** establece el diseño exhaustivo, canónico y normativo de la infraestructura de eventos, observabilidad y métricas del monorepo. Diseñado bajo los estándares más exigentes de ingeniería de datos y producto, este documento y su esquema formal adjunto (`docs/telemetry/event-schemas.json`) definen una taxonomía unificada de **32 eventos telemétricos** (10 eventos obligatorios derivados de las necesidades críticas del negocio y 22 eventos de oportunidad de alta rentabilidad técnica y operativa), agrupados en **7 categorías funcionales**:

1. `inventory` (Gestión de Inventario, Movimientos Kardex y Alertas de Stock)
2. `procurement` (Compras, Aprovisionamiento Inteligente y Proveedores)
3. `sales` (Ventas Multi-Moneda, Operaciones y Monitoreo de Locales)
4. `auth` (Autenticación, Sesiones y Seguridad RBAC)
5. `performance` (Rendimiento de API y Core Web Vitals)
6. `errors` (Diagnóstico de Errores de Negocio, Formulario e Infraestructura)
7. `navigation` (Comportamiento de Usuario, Embudo y Usabilidad del Backoffice)

El diseño incorpora un **Event Envelope común**, una política de **estricta privacidad (Zero PII)**, especificación individual de entrega operativa (**Stream, Batch o Hybrid**), mecanismos de resiliencia (**Throttle, Debounce, Retry exponencial, Deduplicación idempotente y Outbox transaccional**) y una guía inequívoca de instrumentación para los desarrolladores.

---

## 2. Alcance y Exclusiones

### 2.1 Alcance del Encargo
- **Análisis de requerimientos de negocio y arquitectura:** Derivación exhaustiva de métricas indispensables a partir de los dolores operativos expresados por los líderes de departamento (Felipe Guerrero, Lucía Fernández, Mariana Restrepo, Camila Ospina y Nicolás Park).
- **Contratos de datos formales:** Especificación de esquemas en JSON Schema Draft 2020-12 (`docs/telemetry/event-schemas.json`) con validación de tipo, obligatoriedad, formatos, rangos y `additionalProperties: false`.
- **Gobernanza de privacidad y seguridad:** Allowlist estricta campo por campo, seudonimización de identidades, sanitización de textos y exclusión radical de credenciales y datos personales.
- **Estrategia de ingestión y transporte:** Clasificación funcional entre procesamiento en tiempo real (stream), procesamiento en lote (batch) y pipelines híbridos.
- **Guía de instrumentación futura:** Identificación de puntos lógicos exactos en el código existente y en la arquitectura propuesta para habilitar la instrumentación sin ambigüedades.

### 2.2 Exclusiones Explícitas
- **No implementación de código de telemetría:** Este hito es estrictamente de análisis, diseño y documentación técnica. No se implementan SDKs telemétricos (e.g. Segment, OpenTelemetry SDK, Datadog), endpoints recolectores, bases de datos analíticas, brokers de mensajería (Kafka/RabbitMQ) ni emisión real de eventos en los componentes de producción.
- **No alteración de dependencias:** No se añaden librerías npm ni paquetes Python a `package.json` o `pyproject.toml`.
- **No modificación de código de negocio o infraestructura:** Se preservan intactos los servicios existentes en `services/` y `uis/`, así como la configuración de contenedores en `infra/` y `docker-compose.yml`.

---

## 3. Estado Actual del Repositorio

Para garantizar que ningún desarrollador asuma la existencia de servicios inexistentes, se establece la distinción inequívoca entre los tres estados del monorepo:

### 3.1 Flujos Ya Implementados en el Código
- **Backend FastAPI (`services/api`):**
  - **Dominio de Inventario (`app/domains/operations/inventory`):**
    - Modelo relacional PostgreSQL vía SQLModel: `Ingredient`, `IngredientEntry` e `IngredientExit`.
    - Cálculo dinámico de saldo disponible: `current_stock = SUM(entries) - SUM(exits)` por ingrediente y sede (`local_id`). El stock **nunca** se persiste en una columna para garantizar integridad inmutable.
    - Bloqueo pesimista `SELECT ... FOR UPDATE` en PostgreSQL durante salidas (`create_outbound_exit_with_lock`), retornando `HTTP 400 InsufficientStockError` ante saldos insuficientes.
    - Endpoints activos: `GET /inventory/products` (con `local_id`), `POST /inventory/products`, `GET /inventory/products/{id}`, `POST /inventory/orders/inbound`, `POST /inventory/orders/outbound` y `GET /inventory/orders` (con joins $O(1)$ sin problema N+1).
  - **Autenticación y Usuarios (`app/domains/auth`, `app/domains/users`, `app/domains/profiles`):**
    - Persistencia TinyDB (`services/api/data/suppliers.json`), generación de tokens JWT Bearer, dependencias de extracción de usuario (`get_current_user`), registro público, perfil y recuperación de contraseñas vía token de uso único y Resend (`app/domains/auth/email_service.py`).
  - **Proveedores e Incidencias (`app/domains/procurement/suppliers`, `app/domains/incidents`, `app/domains/analytics`):**
    - Catálogo de proveedores en TinyDB, análisis de CSV de incidencias y gestión CRUD de incidencias operativas.
- **Frontend Backoffice (`uis/backoffice`):**
  - Next.js 16 (App Router) con TypeScript y Tailwind.
  - Vistas protegidas bajo `AuthGuard`: `/backoffice/overview`, `/backoffice/inventory/products`, `/backoffice/inventory/orders`, `/backoffice/inventory/orders/inbound`, `/backoffice/inventory/orders/outbound`, `/backoffice/suppliers`, `/backoffice/incidents`.
  - Formularios operativos:
    - `InboundOrderForm`: Selección de sede, ingrediente, cantidad, validación cliente > 0, mutación optimista de saldo en memoria y reconciliación autoritativa con backend.
    - `OutboundOrderForm`: Consulta reactiva de stock disponible, alerta de sobregiro preventiva en UI (bloqueo de botón de envío si `cantidad > stock`), captura inline de `HTTP 400 InsufficientStockError` y mutación optimista.
    - `ProductsTable`: Semáforos textuales de stock (`Agotado` $\le 0$, `Stock bajo` $\le min$, `Saludable` $> min$).
    - `OrdersLedger`: Historial filtrable de entradas y salidas.

### 3.2 Flujos Documentados y Modelados (Capa de Dominio Hito 2)
- **Modelos TypeScript (`src/types/models.ts`) y Utilidades (`src/utils/`):**
  - Entidades formales modeladas: `Local`, `Ingrediente`, `InventarioLocal`, `MovimientoInventario`, `Proveedor`, `OrdenCompra`, `LineaOrden`, `VentaDiaria`, `LineaVenta`, `Receta`, `ComponenteReceta`, `Empleado`, `Cliente`, `ReporteVentasLocal`, `ReporteConsolidado`, `AlertaStock`.
  - Reglas de negocio puras: Coherencia multi-divisa (COP/USD según país), validaciones de salario mínimo, algoritmos de búsqueda lineal y binaria, agregaciones de tickets y alertas de stock.
  - Flujo de Órdenes de Compra: Estados formales `pendiente`, `aprobada`, `enviada`, `recibida`, `cancelada`.

### 3.3 Puntos de Instrumentación Propuestos (Para Implementación Futura)
- **Middleware de telemetría HTTP en FastAPI:** Medición de latencia, inyección de `requestId` y captura de excepciones no controladas.
- **Transactional Outbox en PostgreSQL:** Tabla `telemetry_outbox` para garantizar entrega *at-least-once* de eventos de dominio sin riesgo de inconsistencia ante caídas de red.
- **Workers en segundo plano:** Monitor de inactividad de ventas por local (alerta de cero ventas) y generador programado de sugerencias de compra e informes consolidados semanales.
- **SDK cliente en Next.js:** Buffer en memoria con flush periódico y debounce para eventos de navegación, filtros y Web Vitals.

---

## 4. Fuentes de Verdad y Supuestos

### 4.1 Fuentes Documentales y Equivalencias Canónicas
- `CONTEXT.md`: **Fuente corporativa canónica**. Dado que el archivo mencionado en consignas preliminares como `CONTEXT-empresa.md` no existe en el repositorio, se documenta expresamente que `CONTEXT.md` es la única fuente canónica y fidedigna del negocio de Brasaland.
- `company-choice.md`: Justificación estratégica de selección de problema (Sistema Inteligente de Pedidos de Ingredientes y Reto Bonus de Fidelización).
- `memory-bank/projectbrief.md`: Definición de objetivos de negocio y stakeholders principales.
- `memory-bank/techContext.md`: Restricciones de arquitectura y stack técnico vigente.
- `memory-bank/progress.md`: Registro histórico de hitos completados y estado de entrega.
- `src/types/models.ts`: Modelo canónico de interfaces de TypeScript.
- `services/api`: Código fuente backend FastAPI.
- `uis/backoffice`: Código fuente frontend Next.js.
- **Aclaración crítica sobre incidencias:** El archivo `docs/CONTEXT-brasaland.es.md` **no** debe confundirse con el contexto corporativo general; corresponde exclusiva y taxativamente a las especificaciones del analizador de incidencias operativas de servicio al cliente.

### 4.2 Supuestos Operativos y Técnicos
1. **Red de restaurantes:** Se asumen 14 locales activos: 6 en Colombia (e.g. sedes en Medellín y Bogotá operando en COP) y 8 en Estados Unidos (sur de Florida / Miami operando en USD).
2. **Horario de atención:** El horario operativo habitual de cocina y servicio transcurre entre las 11:00 y las 23:00 hora local de cada restaurante.
3. **Puntos de venta (POS):** Cada restaurante cuenta con terminales POS que registran tickets individuales y transmiten transacciones al backend o generan un cierre diario de caja (`VentaDiaria`).
4. **Zonas horarias y marcas temporales:** Toda marca de tiempo telemétrica (`timestamp`) se genera y persiste en tiempo universal coordinado (UTC) bajo el estándar ISO 8601 con milisegundos (`YYYY-MM-DDTHH:MM:SS.sssZ`). La localización de fecha y hora para supervisores se realiza exclusivamente en la capa de presentación.

---

## 5. Métricas Obligatorias

Alineado con el principio de no inventar métricas arbitrarias, las métricas obligatorias se derivan de forma demostrable a partir de las necesidades explícitas expresadas en `CONTEXT.md`, `company-choice.md` y `memory-bank/projectbrief.md`:

### Métrica Obligatoria 1: Stock y Alertas de Stock Crítico por Local
- **Necesidad de origen:** Felipe Guerrero (Operaciones) señala: *"Ingredient orders are placed by WhatsApp or phone, resulting in overstock in some locations and stockouts in others... automated alerts when a critical ingredient is below minimum threshold"* y *"Reducir quiebres de inventario en ingredientes críticos"* (`CONTEXT.md` §Restaurant Operations; `company-choice.md` §Reto elegido).
- **Métricas derivadas:**
  - `METRIC_STOCK_LEVEL_RATIO`: Proporción de stock disponible respecto al umbral mínimo por ingrediente y sede ($\frac{\text{current\_stock}}{\text{minimum\_stock}}$).
  - `METRIC_CRITICAL_STOCKOUTS_COUNT`: Conteo de eventos donde el stock disponible es menor o igual a cero en horario operativo.
- **Entidades necesarias:** `Local`, `Ingrediente`, `InventarioLocal`, `MovimientoInventario`.
- **Eventos que la alimentan:** `stock_threshold_triggered`, `inbound_order_created`, `outbound_order_created`.
- **Decisión que permite tomar:** Disparar de inmediato órdenes de compra de emergencia antes del turno pico (7:00 PM), pausar platillos en el menú digital o coordinar transferencias directas entre locales cercanos.

### Métrica Obligatoria 2: Generación y Estado de Pedidos de Ingredientes
- **Necesidad de origen:** Lucía Fernández (Compras) y Felipe Guerrero: *"an intelligent ingredient ordering system based on historical sales and current stock... suggested purchase order per local, ready to approve in 1 click -> supervisor approves -> sent to supplier"* (`CONTEXT.md` §Procurement; `company-choice.md` §Flujo completo).
- **Métricas derivadas:**
  - `METRIC_PURCHASE_ORDERS_PIPELINE_COUNT`: Cantidad y valor monetario de órdenes de compra agrupadas por estado (`sugerida`, `aprobada`, `despachada`, `recibida`, `rechazada`).
  - `METRIC_ORDER_APPROVAL_LEAD_TIME_MINUTES`: Tiempo promedio transcurrido entre la generación de una orden sugerida y su aprobación formal por el supervisor.
  - `METRIC_SUPPLIER_FULFILLMENT_CYCLE_HOURS`: Tiempo total desde la aprobación de la orden hasta su recepción física en restaurante.
- **Entidades necesarias:** `OrdenCompra`, `LineaOrden`, `Proveedor`, `Local`, `Ingrediente`.
- **Eventos que la alimentan:** `purchase_order_suggested`, `purchase_order_approved`, `purchase_order_dispatched`, `purchase_order_received`, `purchase_order_rejected`.
- **Decisión que permite tomar:** Identificar cuellos de botella en la aprobación de supervisores (SLA < 30 min), eliminar pedidos informales por WhatsApp y evaluar el cumplimiento de tiempos de entrega de proveedores.

### Métrica Obligatoria 3: Ventas por Local en COP y USD
- **Necesidad de origen:** Felipe Guerrero y Mariana Restrepo (CEO): *"Real-time sales dashboard per location (in COP and USD)"* y *"Mariana cannot answer in real time: how much did we sell this week in Florida? or which location has the highest average ticket this month?"* (`CONTEXT.md` §Restaurant Operations y §Executive Direction).
- **Métricas derivadas:**
  - `METRIC_DAILY_SALES_TOTAL`: Ventas brutas diarias consolidadas y segmentadas por local y divisa nativa (COP y USD), con normalización cambiaria ejecutiva a USD.
  - `METRIC_AVERAGE_TICKET_VALUE`: Ticket promedio por comensal ($\frac{\text{total\_ventas}}{\text{total\_covers}}$) por sede y categoría de consumo.
- **Entidades necesarias:** `Local`, `VentaDiaria`, `LineaVenta`, `Receta`.
- **Eventos que la alimentan:** `daily_sales_recorded`, `pos_order_completed`.
- **Decisión que permite tomar:** Monitoreo ejecutivo diario de ingresos para la CEO, calibración de precios dinámicos según país y evaluación de rentabilidad comparativa entre Colombia y Florida.

### Métrica Obligatoria 4: Locales sin Ventas Durante Horario Operativo
- **Necesidad de origen:** Felipe Guerrero: *"automated alerts when a location shows no sales during opening hours"* (`CONTEXT.md` §Restaurant Operations).
- **Métricas derivadas:**
  - `METRIC_OPERATING_IDLE_MINUTES`: Minutos consecutivos transcurridos dentro del horario oficial de servicio de un local sin registrar ninguna transacción en el punto de venta.
  - `METRIC_ZERO_SALES_INCIDENTS_COUNT`: Número de alertas de inactividad anómala activadas por sede en el mes.
- **Entidades necesarias:** `Local`, `VentaDiaria`, `HorarioOperativo`.
- **Eventos que la alimentan:** `location_zero_sales_alert_triggered`, `pos_heartbeat_recorded`, `pos_order_completed`.
- **Decisión que permite tomar:** Intervención operativa inmediata del supervisor de zona ante contingencias críticas: corte de energía, caída de conectividad de red, falla del hardware de caja POS o apertura tardía no reportada.

### Métrica Obligatoria 5: Visibilidad Consolidada de Compras y Proveedores
- **Necesidad de origen:** Lucía Fernández: *"supplier management platform with price history and alerts, and consolidated purchasing visibility to enable central negotiations across both markets... weekly report for Lucía with consolidated orders to negotiate volume with the ~20 suppliers"* (`CONTEXT.md` §Procurement and Suppliers; `company-choice.md` §Impacto esperado).
- **Métricas derivadas:**
  - `METRIC_CONSOLIDATED_SPEND_BY_SUPPLIER`: Gasto total acumulado por proveedor, categoría de insumo y país en COP y USD.
  - `METRIC_SUPPLIER_PRICE_VARIANCE_RATIO`: Porcentaje de discrepancia entre el precio unitario facturado y el precio contratado en catálogo ($\frac{\text{precio\_factura} - \text{precio\_pactado}}{\text{precio\_pactado}} \times 100$).
- **Entidades necesarias:** `Proveedor`, `OrdenCompra`, `LineaOrden`, `Ingrediente`.
- **Eventos que la alimentan:** `supplier_price_variance_detected`, `purchase_order_received`, `consolidated_procurement_report_generated`.
- **Decisión que permite tomar:** Negociación centralizada de descuentos por volumen consolidado en Colombia y Florida con los ~20 proveedores, rechazo preventivo de facturas con sobreprecio injustificado y penalización contractual por incumplimiento de SLA.

---

## 6. Matriz de Trazabilidad Métrica → Evento → Decisión

| Requisito / Dolor de Origen | Métrica Derivada | Entidades Necesarias | Eventos Productores | Decisión Habilitada |
| :--- | :--- | :--- | :--- | :--- |
| Quiebres de stock en cocina a las 7:00 PM y sobrestock en otras sedes (`CONTEXT.md`). | `METRIC_STOCK_LEVEL_RATIO`<br>`METRIC_CRITICAL_STOCKOUTS_COUNT` | `Local`<br>`Ingrediente`<br>`InventarioLocal`<br>`MovimientoInventario` | `stock_threshold_triggered`<br>`inbound_order_created`<br>`outbound_order_created` | Disparar reabastecimiento urgente de ingredientes críticos; pausar platos agotados en menú; coordinar traslados entre sedes. |
| Pedidos informales por WhatsApp sin trazabilidad ni optimización (`company-choice.md`). | `METRIC_PURCHASE_ORDERS_PIPELINE`<br>`METRIC_ORDER_APPROVAL_LEAD_TIME`<br>`METRIC_SUPPLIER_FULFILLMENT_CYCLE` | `OrdenCompra`<br>`LineaOrden`<br>`Proveedor`<br>`Local`<br>`Ingrediente` | `purchase_order_suggested`<br>`purchase_order_approved`<br>`purchase_order_dispatched`<br>`purchase_order_received`<br>`purchase_order_rejected` | Erradicar WhatsApp en compras; garantizar aprobación de supervisores en < 30 min; auditar lead time de proveedores. |
| Falta de visibilidad de ventas en COP y USD en tiempo real para CEO (`CONTEXT.md`). | `METRIC_DAILY_SALES_TOTAL`<br>`METRIC_AVERAGE_TICKET_VALUE` | `Local`<br>`VentaDiaria`<br>`LineaVenta`<br>`Receta` | `daily_sales_recorded`<br>`pos_order_completed` | Seguimiento ejecutivo diario de metas de ventas; comparación de márgenes entre Colombia y USA; ajuste dinámico de menú. |
| Locales abiertos sin registrar ventas en horario operativo (`CONTEXT.md`). | `METRIC_OPERATING_IDLE_MINUTES`<br>`METRIC_ZERO_SALES_INCIDENTS_COUNT` | `Local`<br>`VentaDiaria`<br>`TerminalPOS` | `location_zero_sales_alert_triggered`<br>`pos_heartbeat_recorded`<br>`pos_order_completed` | Contactar al local en < 15 min ante sospecha de corte de internet, caída de caja POS o emergencia operativa en cocina. |
| Lucía se entera del aumento de precios cuando llega la factura (`CONTEXT.md`). | `METRIC_CONSOLIDATED_SPEND_BY_SUPPLIER`<br>`METRIC_SUPPLIER_PRICE_VARIANCE_RATIO` | `Proveedor`<br>`OrdenCompra`<br>`LineaOrden`<br>`Ingrediente` | `supplier_price_variance_detected`<br>`purchase_order_received`<br>`consolidated_procurement_report_generated` | Reclamar sobrecostos antes del pago; negociar precios mayoristas por volumen agregado de las 14 sedes con los 20 proveedores. |
| Rechazos de consumo de stock por falta de saldo en sistema (`services/api`). | `METRIC_INSUFFICIENT_STOCK_ATTEMPTS_COUNT` | `Local`<br>`Ingrediente`<br>`MovimientoInventario` | `outbound_insufficient_stock_attempted` | Auditar desviaciones entre stock físico y teórico; detectar mermas no declaradas o recetas mal calibradas. |
| Protección de integridad del kardex contable inmutable (`services/api`). | `METRIC_DIRECT_STOCK_EDIT_VIOLATIONS` | `Local`<br>`Ingrediente` | `direct_stock_edit_rejected` | Bloquear peticiones de API que intenten modificar stock directamente sin generar un movimiento de entrada o salida. |
| Sesiones caducadas y fricción de acceso en supervisores (`uis/backoffice`). | `METRIC_SESSION_EXPIRATION_RATE` | `User`<br>`Session` | `session_expired`<br>`user_logged_in` | Optimizar tiempo de vida del JWT y refresh tokens para evitar pérdida de datos mientras se llena un formulario en cocina. |
| Latencia en consulta de ingredientes en sede (`services/api`). | `METRIC_API_P95_LATENCY_MS` | `Endpoint`<br>`Database` | `api_latency_recorded`<br>`db_query_slow_detected` | Identificar degradación en consultas de inventario antes de que el supervisor experimente lentitud en el restaurante. |

---

## 7. Mapa de Entidades y Flujos

### 7.1 Arquitectura del Flujo de Inventario y Telemetría
El siguiente diagrama ilustra el ciclo de vida operativo del inventario en Brasaland y los puntos exactos de emisión de telemetría:

```mermaid
flowchart TD
    subgraph POS_Service["Servicio en Restaurante"]
        POS["Venta en TPV / Comanda"] -->|Emite pos_order_completed| POS_EVT["pos_order_completed"]
        POS --> REC_EXP["Explosión de Recetas (Consumo Teórico)"]
    end

    subgraph Backoffice_Operations["Operaciones en Cocina / Backoffice"]
        KITCHEN["Registro de Salida (Outbound)"] --> OUT_FORM["OutboundOrderForm (UI)"]
        OUT_FORM -->|Saldo Insuficiente en UI| EVT_OVERSTOCK_UI["outbound_insufficient_stock_attempted (client_form_guard)"]
        OUT_FORM -->|Petición POST /inventory/orders/outbound| API_OUT["FastAPI: create_outbound_order"]
        API_OUT -->|Pessimistic Lock & Stock Check| LOCK_CHECK{"¿Stock >= Cantidad?"}
        LOCK_CHECK -- No --> HTTP400["HTTP 400 InsufficientStockError"]
        HTTP400 -->|Emite| EVT_LOCK_FAIL["outbound_insufficient_stock_attempted (backend_lock)"]
        LOCK_CHECK -- Sí --> WRITE_EXIT["Persiste IngredientExit en PostgreSQL"]
        WRITE_EXIT -->|Emite| EVT_OUT["outbound_order_created"]
        WRITE_EXIT --> THRESH_CHECK{"¿Saldo <= Mínimo?"}
        THRESH_CHECK -- Sí -->|Emite| EVT_THRESH["stock_threshold_triggered"]
    end

    subgraph AI_Procurement["Motor Inteligente de Compras"]
        EVT_THRESH --> AGENT_AI["Agente Predictivo de Reabastecimiento"]
        POS_EVT --> AGENT_AI
        AGENT_AI -->|Calcula Demanda vs Stock| PO_SUGG["Genera Orden Sugerida"]
        PO_SUGG -->|Emite| EVT_PO_SUGG["purchase_order_suggested"]
        EVT_PO_SUGG --> SUP_APPROVAL["Supervisor Revisa en Backoffice"]
        SUP_APPROVAL -- Rechaza -->|Emite| EVT_PO_REJ["purchase_order_rejected"]
        SUP_APPROVAL -- Aprueba 1-Clic -->|Emite| EVT_PO_APP["purchase_order_approved"]
        EVT_PO_APP --> DISPATCH["Despacho a Proveedor"]
        DISPATCH -->|Emite| EVT_PO_DISP["purchase_order_dispatched"]
    end

    subgraph Reception["Recepción Física en Sede"]
        TRUCK["Llegada de Camión con Insumos"] --> IN_FORM["InboundOrderForm (UI)"]
        IN_FORM -->|Petición POST /inventory/orders/inbound| API_IN["FastAPI: create_inbound_order"]
        API_IN --> WRITE_ENTRY["Persiste IngredientEntry en PostgreSQL"]
        WRITE_ENTRY -->|Emite| EVT_IN["inbound_order_created"]
        WRITE_ENTRY --> PO_MATCH["Conciliación con Orden de Compra"]
        PO_MATCH -->|Emite| EVT_PO_REC["purchase_order_received"]
        PO_MATCH --> PRICE_CHECK{"¿Precio Factura == Catálogo?"}
        PRICE_CHECK -- Discrepancia -->|Emite| EVT_PRICE_VAR["supplier_price_variance_detected"]
    end
```

### 7.2 Entidades de Dominio Observadas
- **`Local`**: Nodo de partición física del negocio (`id`, `nombre`, `ciudad`, `pais`, `monedaLocal`, `activo`).
- **`Ingrediente`**: Catálogo centralizado de artículos (`id`, `sku`, `name`, `category`, `unit_of_measure`, `minimum_stock`, `perishable`).
- **`InventarioLocal` / Movimiento Inmutable**: Partición de saldo dinámico en PostgreSQL (`IngredientEntry` e `IngredientExit`) asociada a una sede y auditada con el `user_uuid` del operador.
- **`Proveedor`**: Entidad externa de suministro (`id`, `nombre`, `pais`, `moneda`, `tiempoEntregaDias`, `montoMinimoOrden`).
- **`OrdenCompra`**: Documento transaccional de abastecimiento (`id`, `localId`, `proveedorId`, `estado`, `lineas`, `totalOrden`, `moneda`).
- **`VentaDiaria`**: Cierre consolidado de ingresos de restaurante (`id`, `localId`, `fecha`, `totalVenta`, `moneda`, `totalCovers`).
- **`UserSession`**: Contexto del colaborador autenticado (`userId`, `sessionId`, `userRole`, `assignedLocalId`).

---

## 8. Catálogo Completo de Eventos

A continuación se presentan los **32 eventos telemétricos aceptados**, clasificados según su obligatoriedad (`mandatory` vs `opportunity`), con su hipótesis de negocio formal y su decisión concreta habilitada.

### 8.1 Categoría `inventory` (8 eventos)

#### 1. `inbound_order_created`
- **Clasificación:** `mandatory`
- **Acción:** `created`
- **Justificación Formal:**
  > Capturamos `inbound_order_created` porque necesitamos saber el volumen exacto y la hora en que ingresan insumos físicos a cada sede, lo que permite actualizar el balance de stock disponible en tiempo real y habilitar insumos para el turno de cocina.
- **Productor:** Backend FastAPI (`create_inbound_order` en `services/api`) y Backoffice (`InboundOrderForm`).
- **Consumidor:** Dashboard de inventario, visualizador de stock en cocina y reconciliación contable.
- **Estrategia de Entrega:** `hybrid` (Stream para saldo inmediato; Batch para consolidación mensual).

#### 2. `outbound_order_created`
- **Clasificación:** `mandatory`
- **Acción:** `created`
- **Justificación Formal:**
  > Capturamos `outbound_order_created` porque necesitamos saber cuánto inventario se consume o desecha operativamente en cada restaurante, lo que permite calcular el saldo remanente verificado bajo bloqueo pesimista y proyectar el ritmo de consumo.
- **Productor:** Backend FastAPI (`create_outbound_order` en `services/api`) y Backoffice (`OutboundOrderForm`).
- **Consumidor:** Motor de alertas de quiebre y costeo de recetas.
- **Estrategia de Entrega:** `hybrid` (Stream para disparo de alertas de umbral; Batch para costeo semanal).

#### 3. `stock_threshold_triggered`
- **Clasificación:** `mandatory`
- **Acción:** `triggered`
- **Justificación Formal:**
  > Capturamos `stock_threshold_triggered` porque necesitamos saber cuándo un ingrediente cae por debajo del stock mínimo o se agota en una sede, lo que permite disparar alertas prioritarias a supervisores y activar pedidos de reabastecimiento antes de las 7:00 PM.
- **Productor:** Backend FastAPI (post-transacción de salida) y worker de monitoreo de umbrales.
- **Consumidor:** Canal de alertas de supervisor (WhatsApp/Push) y agente inteligente de compras.
- **Estrategia de Entrega:** `stream` (Latencia crítica < 5 segundos).

#### 4. `outbound_insufficient_stock_attempted`
- **Clasificación:** `opportunity`
- **Acción:** `attempted`
- **Justificación Formal:**
  > Capturamos `outbound_insufficient_stock_attempted` porque necesitamos saber cuándo y qué insumos se intentan retirar sin contar con stock suficiente en el sistema, lo que permite identificar descuadres entre el inventario físico y teórico o recetas mal costeadas.
- **Productor:** Frontend Backoffice (`OutboundOrderForm` guard) y Backend FastAPI (captura de `InsufficientStockError`).
- **Consumidor:** Panel de auditoría de mermas y supervisor de operaciones.
- **Estrategia de Entrega:** `stream` (Latencia < 10 segundos).

#### 5. `direct_stock_edit_rejected`
- **Clasificación:** `opportunity`
- **Acción:** `rejected`
- **Justificación Formal:**
  > Capturamos `direct_stock_edit_rejected` porque necesitamos saber si algún usuario o proceso intenta mutar directamente las columnas de inventario sin generar un movimiento kardex, lo que permite proteger la inmutabilidad arquitectónica y auditar anomalías de integridad.
- **Productor:** Backend FastAPI (guardia de enrutador o middleware de seguridad).
- **Consumidor:** Auditoría de seguridad y alertas DevOps.
- **Estrategia de Entrega:** `stream` (Latencia < 5 segundos).

#### 6. `inventory_catalog_viewed`
- **Clasificación:** `opportunity`
- **Acción:** `viewed`
- **Justificación Formal:**
  > Capturamos `inventory_catalog_viewed` porque necesitamos saber con qué frecuencia y en qué sedes los supervisores inspeccionan su inventario, lo que permite evaluar la diligencia operativa por sede y correlacionarla con la tasa de quiebres.
- **Productor:** Frontend Backoffice (`ProductsTable` en `uis/backoffice`).
- **Consumidor:** Métricas de adopción de backoffice y supervisión de restaurantes.
- **Estrategia de Entrega:** `batch` (Bufferizado en cliente cada 60 segundos).

#### 7. `ingredient_detail_queried`
- **Clasificación:** `opportunity`
- **Acción:** `queried`
- **Justificación Formal:**
  > Capturamos `ingredient_detail_queried` porque necesitamos saber cuáles ingredientes específicos generan mayor consulta manual por parte del equipo, lo que permite identificar artículos con saldos confusos o alta variabilidad para ajustar sus parámetros.
- **Productor:** Frontend Backoffice / Backend FastAPI (`GET /inventory/products/{id}`).
- **Consumidor:** Optimizador de catálogo y parámetros de stock mínimo.
- **Estrategia de Entrega:** `batch` (Bufferizado periódico).

#### 8. `inventory_filter_applied`
- **Clasificación:** `opportunity`
- **Acción:** `applied`
- **Justificación Formal:**
  > Capturamos `inventory_filter_applied` porque necesitamos saber qué categorías y criterios de búsqueda utilizan los supervisores en las tablas, lo que permite optimizar la jerarquía de navegación y los filtros por defecto de la interfaz.
- **Productor:** Frontend Backoffice (`ProductsTable` / `OrdersLedger`).
- **Consumidor:** Analítica de experiencia de usuario (UX).
- **Estrategia de Entrega:** `batch` (Debounced 500 ms; flush agrupado).

---

### 8.2 Categoría `procurement` (7 eventos)

#### 9. `purchase_order_suggested`
- **Clasificación:** `mandatory`
- **Acción:** `suggested`
- **Justificación Formal:**
  > Capturamos `purchase_order_suggested` porque necesitamos saber qué pedidos de compra sugiere automáticamente el agente de IA para cada sede, lo que permite reemplazar los cálculos manuales y pedidos desordenados por WhatsApp.
- **Productor:** Agente inteligente de aprovisionamiento / Worker de compras.
- **Consumidor:** Bandeja de entrada de órdenes en backoffice y evaluación de precisión predictiva.
- **Estrategia de Entrega:** `hybrid` (Stream para supervisor al iniciar turno; Batch para benchmarking del modelo).

#### 10. `purchase_order_approved`
- **Clasificación:** `mandatory`
- **Acción:** `approved`
- **Justificación Formal:**
  > Capturamos `purchase_order_approved` porque necesitamos saber cuándo un supervisor autoriza formalmente una compra y con qué tiempo de respuesta, lo que permite medir el cumplimiento del SLA de aprobación (< 30 min) y disparar el envío al proveedor.
- **Productor:** Backend FastAPI / Backoffice Compras.
- **Consumidor:** Despachador automático a proveedores y dashboard de Lucía Fernández.
- **Estrategia de Entrega:** `stream` (Latencia < 5 segundos).

#### 11. `purchase_order_dispatched`
- **Clasificación:** `opportunity`
- **Acción:** `dispatched`
- **Justificación Formal:**
  > Capturamos `purchase_order_dispatched` porque necesitamos saber el momento y canal por el cual se transmitió la orden al proveedor, lo que permite activar el cronómetro de lead time acordado por contrato.
- **Productor:** Worker de despacho de órdenes de compra.
- **Consumidor:** Tracker de entrega y SLA de proveedores.
- **Estrategia de Entrega:** `stream` (Latencia < 15 segundos).

#### 12. `purchase_order_received`
- **Clasificación:** `mandatory`
- **Acción:** `received`
- **Justificación Formal:**
  > Capturamos `purchase_order_received` porque necesitamos saber si el proveedor cumplió en tiempo y forma con el pedido en la sede, lo que permite calificar el nivel de servicio y respaldar las negociaciones anuales de compras.
- **Productor:** Backend FastAPI / Backoffice al asociar una orden de entrada a una orden de compra.
- **Consumidor:** Matriz de calificación de proveedores de Lucía Fernández.
- **Estrategia de Entrega:** `hybrid` (Stream para entrada a stock; Batch para cálculo de score).

#### 13. `purchase_order_rejected`
- **Clasificación:** `opportunity`
- **Acción:** `rejected`
- **Justificación Formal:**
  > Capturamos `purchase_order_rejected` porque necesitamos saber qué propuestas de compra son rechazadas por los supervisores y por qué motivo, lo que permite calibrar los algoritmos de predicción de demanda de la IA.
- **Productor:** Backend FastAPI / Backoffice Compras.
- **Consumidor:** Pipeline de reentrenamiento de algoritmos de abastecimiento.
- **Estrategia de Entrega:** `batch` (Latencia 1 hora).

#### 14. `supplier_price_variance_detected`
- **Clasificación:** `mandatory`
- **Acción:** `detected`
- **Justificación Formal:**
  > Capturamos `supplier_price_variance_detected` porque necesitamos saber cuándo un proveedor incrementa sus precios en factura frente a lo pactado en contrato, lo que permite congelar pagos indebidos y alertar al departamento de compras en tiempo real.
- **Productor:** Servicio de verificación de facturas en backend (`services/api`).
- **Consumidor:** Alerta prioritaria para Lucía Fernández y módulo de cuentas por pagar.
- **Estrategia de Entrega:** `stream` (Latencia < 60 segundos).

#### 15. `consolidated_procurement_report_generated`
- **Clasificación:** `opportunity`
- **Acción:** `generated`
- **Justificación Formal:**
  > Capturamos `consolidated_procurement_report_generated` porque necesitamos saber el volumen agregado semanal de compras de toda la cadena, lo que permite a la gerencia de compras negociar precios por volumen mayorista ante los 20 proveedores comunes.
- **Productor:** Worker batch semanal programado (Lunes 07:00 UTC).
- **Consumidor:** Dirección ejecutiva (Mariana Restrepo) y compras (Lucía Fernández).
- **Estrategia de Entrega:** `batch` (Ejecución programada semanal).

---

### 8.3 Categoría `sales` (4 eventos)

#### 16. `daily_sales_recorded`
- **Clasificación:** `mandatory`
- **Acción:** `recorded`
- **Justificación Formal:**
  > Capturamos `daily_sales_recorded` porque necesitamos saber los ingresos consolidados de cada sede en su divisa nativa (COP o USD) y el total de comensales atendidos, lo que permite calcular el ticket promedio y alimentar el cálculo de consumo de ingredientes.
- **Productor:** Servicio de cierre de jornada en backend (`services/api`).
- **Consumidor:** Data warehouse corporativo, tablero ejecutivo y motor de predicción.
- **Estrategia de Entrega:** `batch` (Procesamiento nocturno diario).

#### 17. `pos_order_completed`
- **Clasificación:** `mandatory`
- **Acción:** `recorded`
- **Justificación Formal:**
  > Capturamos `pos_order_completed` porque necesitamos saber los platillos vendidos en tiempo real en los terminales de punto de venta, lo que permite ejecutar la explosión de recetas para descontar insumos teóricos y proyectar el stock intra-día.
- **Productor:** Gateway de integración POS en restaurante.
- **Consumidor:** Servicio de deducción teórica de ingredientes y tablero de ventas en vivo.
- **Estrategia de Entrega:** `stream` (Latencia < 2 segundos).

#### 18. `location_zero_sales_alert_triggered`
- **Clasificación:** `mandatory`
- **Acción:** `triggered`
- **Justificación Formal:**
  > Capturamos `location_zero_sales_alert_triggered` porque necesitamos saber de inmediato si un restaurante operativo no registra ninguna venta durante horario de servicio, lo que permite al Director de Operaciones intervenir ante caídas del POS, cortes de luz o emergencias.
- **Productor:** Worker de monitoreo de actividad en `services/api`.
- **Consumidor:** Alerta prioritaria a Felipe Guerrero (Director de Operaciones).
- **Estrategia de Entrega:** `stream` (Latencia < 30 segundos tras superar umbral de inactividad).

#### 19. `pos_heartbeat_recorded`
- **Clasificación:** `opportunity`
- **Acción:** `recorded`
- **Justificación Formal:**
  > Capturamos `pos_heartbeat_recorded` porque necesitamos saber si el terminal de caja en restaurante se encuentra en línea o en modo desconectado, lo que permite discriminar entre un local sin clientes y un fallo de telecomunicaciones.
- **Productor:** Agente de software local en el terminal POS de la sede.
- **Consumidor:** Monitor de infraestructura de red y soporte de sistemas.
- **Estrategia de Entrega:** `stream` (Latencia 60 segundos).

---

### 8.4 Categoría `auth` (5 eventos)

#### 20. `user_logged_in`
- **Clasificación:** `mandatory`
- **Acción:** `logged_in`
- **Justificación Formal:**
  > Capturamos `user_logged_in` porque necesitamos saber qué usuarios ingresan al sistema, con qué rol operativo y en qué sede, lo que permite auditar la autoría de las transacciones de inventario y compras.
- **Productor:** Backend FastAPI (`/auth/login`) y Backoffice (`AuthProvider`).
- **Consumidor:** Registro de auditoría de seguridad y trazabilidad de turnos.
- **Estrategia de Entrega:** `hybrid` (Stream para control de accesos simultáneos; Batch para retención).

#### 21. `user_login_failed`
- **Clasificación:** `opportunity`
- **Acción:** `failed`
- **Justificación Formal:**
  > Capturamos `user_login_failed` porque necesitamos saber cuándo se presentan intentos de inicio de sesión con credenciales erróneas, lo que permite activar bloqueos temporales por IP/cuenta para mitigar ataques de fuerza bruta.
- **Productor:** Backend FastAPI (`app/domains/auth/service.py`).
- **Consumidor:** Sistema SIEM de seguridad y rate limiter.
- **Estrategia de Entrega:** `stream` (Latencia < 2 segundos).

#### 22. `session_expired`
- **Clasificación:** `opportunity`
- **Acción:** `expired`
- **Justificación Formal:**
  > Capturamos `session_expired` porque necesitamos saber con qué frecuencia expiran los tokens de acceso de supervisores durante la operación, lo que permite ajustar las ventanas de expiración del JWT para no interrumpir el registro de cocina.
- **Productor:** Frontend Backoffice (interceptor HTTP 401 en `src/lib/inventory.ts`).
- **Consumidor:** Telemetría de experiencia de usuario y configuración de sesiones.
- **Estrategia de Entrega:** `batch` (Bufferizado en cliente).

#### 23. `permission_denied`
- **Clasificación:** `opportunity`
- **Acción:** `denied`
- **Justificación Formal:**
  > Capturamos `permission_denied` porque necesitamos saber si colaboradores intentan acceder a recursos restringidos (HTTP 403), lo que permite identificar fallas de asignación de roles o intentos indebidos de manipulación de compras.
- **Productor:** Backend FastAPI (`get_current_user` dependencies) y Backoffice `AuthGuard`.
- **Consumidor:** Auditoría de cumplimiento normativo y control de privilegios.
- **Estrategia de Entrega:** `stream` (Latencia < 5 segundos).

#### 24. `password_reset_requested`
- **Clasificación:** `opportunity`
- **Acción:** `requested`
- **Justificación Formal:**
  > Capturamos `password_reset_requested` porque necesitamos saber el volumen de peticiones de recuperación de contraseña, lo que permite auditar la estabilidad del servicio transaccional de correo y detectar abusos de enumeración.
- **Productor:** Backend FastAPI (`/auth/forgot-password`).
- **Consumidor:** Monitor de correos transaccionales y soporte técnico.
- **Estrategia de Entrega:** `hybrid` (Stream para alertas de fallo de envío; Batch para conteo semanal).

---

### 8.5 Categoría `performance` (3 eventos)

#### 25. `api_latency_recorded`
- **Clasificación:** `opportunity`
- **Acción:** `recorded`
- **Justificación Formal:**
  > Capturamos `api_latency_recorded` porque necesitamos conocer los tiempos de respuesta (p50, p95, p99) de los endpoints de inventario y órdenes, lo que permite optimizar consultas a la base de datos antes de que ralenticen la operativa en restaurante.
- **Productor:** Middleware de observabilidad en FastAPI (`services/api`).
- **Consumidor:** Tableros APM / Grafana y equipo de ingeniería.
- **Estrategia de Entrega:** `batch` (Agregado en memoria y enviado en flush cada 30-60 segundos).

#### 26. `client_web_vitals_recorded`
- **Clasificación:** `opportunity`
- **Acción:** `recorded`
- **Justificación Formal:**
  > Capturamos `client_web_vitals_recorded` porque necesitamos saber cómo rinde la interfaz del backoffice en los dispositivos móviles de los supervisores en cocina, lo que permite priorizar optimizaciones de carga y reducir el tiempo de renderizado.
- **Productor:** Frontend Backoffice (`uis/backoffice` con Web Vitals reporter).
- **Consumidor:** Monitoreo de calidad frontend.
- **Estrategia de Entrega:** `batch` (Bufferizado en cliente y transmitido en `visibilitychange`).

#### 27. `db_query_slow_detected`
- **Clasificación:** `opportunity`
- **Acción:** `detected`
- **Justificación Formal:**
  > Capturamos `db_query_slow_detected` porque necesitamos saber qué consultas o agrupaciones sobre la tabla de movimientos superan los 200 ms, lo que permite añadir índices o particionar tablas antes de causar lentitud transaccional.
- **Productor:** Listener de SQLAlchemy/SQLModel en backend (`services/api`).
- **Consumidor:** Alertas de rendimiento para DBA y equipo de backend.
- **Estrategia de Entrega:** `stream` (Latencia < 15 segundos).

---

### 8.6 Categoría `errors` (3 eventos)

#### 28. `form_validation_failed`
- **Clasificación:** `opportunity`
- **Acción:** `failed`
- **Justificación Formal:**
  > Capturamos `form_validation_failed` porque necesitamos saber qué campos de los formularios de entrada y salida generan mayor confusión en los usuarios, lo que permite rediseñar los campos y reducir errores humanos en el pesaje de insumos.
- **Productor:** Frontend Backoffice (`InboundOrderForm` y `OutboundOrderForm`).
- **Consumidor:** Equipo de producto y diseño UX.
- **Estrategia de Entrega:** `batch` (Bufferizado en cliente).

#### 29. `system_exception_captured`
- **Clasificación:** `opportunity`
- **Acción:** `captured`
- **Justificación Formal:**
  > Capturamos `system_exception_captured` porque necesitamos saber qué errores 500 no controlados ocurren en los servicios, lo que permite a la guardia técnica corregir fallas críticas de infraestructura sin depender de reportes informales.
- **Productor:** Exception Handler global de FastAPI (`services/api/app/main.py`).
- **Consumidor:** Guardia de ingeniería / Sentry / Alertas Slack.
- **Estrategia de Entrega:** `stream` (Latencia < 5 segundos).

#### 30. `external_integration_failed`
- **Clasificación:** `opportunity`
- **Acción:** `failed`
- **Justificación Formal:**
  > Capturamos `external_integration_failed` porque necesitamos saber cuándo fallan las comunicaciones con pasarelas externas (Resend, WhatsApp API o TPVs), lo que permite activar reintentos automáticos y conmutar a canales secundarios de contingencia.
- **Productor:** Módulos de integración en backend (`services/api`).
- **Consumidor:** Circuit breaker y monitor de integraciones externas.
- **Estrategia de Entrega:** `stream` (Latencia < 10 segundos).

---

### 8.7 Categoría `navigation` (2 eventos)

#### 31. `backoffice_page_viewed`
- **Clasificación:** `opportunity`
- **Acción:** `viewed`
- **Justificación Formal:**
  > Capturamos `backoffice_page_viewed` porque necesitamos saber qué módulos del backoffice son los más utilizados y cuánto tiempo pasa un usuario en cada sección, lo que permite simplificar la navegación para las tareas diarias de los supervisores.
- **Productor:** Next.js Router Listener en `uis/backoffice`.
- **Consumidor:** Análisis de embudo de usabilidad y producto.
- **Estrategia de Entrega:** `batch` (Bufferizado periódico).

#### 32. `form_abandoned`
- **Clasificación:** `opportunity`
- **Acción:** `abandoned`
- **Justificación Formal:**
  > Capturamos `form_abandoned` porque necesitamos saber con qué frecuencia los supervisores inician el llenado de una orden y lo abandonan sin completarlo, lo que permite diseñar mecanismos de auto-guardado local para no perder avances ante distracciones en cocina.
- **Productor:** Hook de formulario en `uis/backoffice` (`beforeunload` / route change).
- **Consumidor:** Diseño de interacción y UX de cocina.
- **Estrategia de Entrega:** `batch` (Flush al cambiar de vista).

---

## 9. Event Envelope

Todos los eventos del ecosistema Brasaland deben cumplir de manera estricta con el **Event Envelope Unificado**. No se permite ningún dato específico del evento fuera del objeto `properties`.

### 9.1 Estructura Canónica del Envelope

```json
{
  "eventId": "c8d4e92a-7b3f-4c5e-9e12-8a9b1c2d3e4f",
  "timestamp": "2026-09-22T14:30:00.000Z",
  "sessionId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "userId": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "event_type": "inbound_order_created",
  "entity_action": "created",
  "schemaVersion": "1.0.0",
  "requestId": "e2a74c10-98cc-4372-a567-0e02b2c3d479",
  "properties": {
    "order_id": "11111111-2222-3333-4444-555555555555",
    "local_id": "MED-001",
    "ingredient_id": "66666666-7777-8888-9999-000000000000",
    "ingredient_sku": "ING-001",
    "quantity": 25.5,
    "unit_of_measure": "kg",
    "previous_stock": 10.0,
    "resulting_stock": 35.5
  }
}
```

### 9.2 Especificación de Campos del Envelope

| Campo | Tipo | Obligatorio | Nullable | Generador | Propósito y Reglas |
| :--- | :--- | :---: | :---: | :--- | :--- |
| `eventId` | `string` (UUID v4) | Sí | No | Emisor (Frontend / Backend) | Identificador único e inmutable del evento. Utilizado para deduplicación idempotente en la capa de ingestión. |
| `timestamp` | `string` (date-time) | Sí | No | Emisor (Reloj UTC) | Fecha y hora exacta del suceso en formato ISO 8601 UTC estricto (`YYYY-MM-DDTHH:MM:SS.sssZ`). |
| `sessionId` | `string` \| `null` | Sí | Sí | Contexto de Autenticación | UUID de sesión web activa. Se establece como `null` en eventos de sistema o crons sin sesión interactiva. |
| `userId` | `string` (UUID) \| `null` | Sí | Sí | Contexto de Usuario | Identificador seudonimizado estable del usuario interno (`user_uuid`). Se establece como `null` en eventos automáticos de background. |
| `event_type` | `string` (snake_case) | Sí | No | Emisor / Contrato | Nombre único del evento según la taxonomía oficial (`<entity>_<action>`). |
| `entity_action` | `string` (verbo) | Sí | No | Emisor / Contrato | Verbo normalizado de la acción realizada (e.g. `created`, `triggered`, `rejected`, `recorded`). |
| `schemaVersion` | `string` (SemVer) | Sí | No | Contrato | Versión semántica del contrato del evento (`MAJOR.MINOR.PATCH`, e.g. `1.0.0`). |
| `requestId` | `string` | Sí | No | Gateway / Middleware | Identificador de correlación distribuida propagado en encabezados `X-Request-ID` o W3C `traceparent`. |
| `properties` | `object` | Sí | No | Emisor / Dominio | Carga útil específica del evento, regulada por su allowlist estricta (`additionalProperties: false`). |

---

## 10. Taxonomía y Versionado

### 10.1 Convención de Nombres
La taxonomía adopta el estándar estricto en `snake_case` con la estructura semántica:
$$\text{<entidad>}\_\text{<acción>}$$

Se prohíben sinónimos ambiguos para un mismo suceso. Por ejemplo, no se permite alternar entre `created`, `submitted` y `started`. Cada verbo posee un significado unívoco:
- `created`: Creación y persistencia efectiva de un registro transaccional en base de datos.
- `triggered`: Activación automática de una alerta por superación de un umbral o condición operativa.
- `attempted`: Intento de realizar una acción que fue bloqueada o rechazada antes o durante su procesamiento.
- `rejected`: Decisión explícita de descarte o rechazo formal de una entidad por política de negocio.
- `recorded`: Captura pasiva o consolidación periódica de una métrica de rendimiento, telemetría o venta.
- `viewed`: Renderizado completo y visualización activa de una pantalla o catálogo por el usuario.
- `queried`: Consulta granular de información específica de un recurso.
- `applied`: Aplicación de filtros o parámetros de búsqueda en la interfaz.
- `suggested`: Emisión de una recomendación automatizada por algoritmos de IA.
- `approved`: Autorización humana de una orden o cambio de estado.
- `dispatched`: Envío hacia un destinatario externo (proveedor).
- `received`: Recepción física o confirmación de entrega en destino.
- `detected`: Identificación de una anomalía o discrepancia por comparación lógica.
- `generated`: Creación y cierre de un artefacto consolidado o informe agregado.
- `logged_in`: Establecimiento exitoso de identidad autenticada.
- `failed`: Ocurrencia de un fallo tipificado en un proceso o integración.
- `expired`: Caducidad temporal de un token, credencial o sesión.
- `denied`: Bloqueo de acceso por restricciones de autorización o permisos RBAC.
- `requested`: Solicitud formal de inicio de un flujo secundario (recuperación de acceso).
- `captured`: Atrapamiento controlado de una excepción técnica del sistema.
- `abandoned`: Salida de una interfaz de formulario sin haber enviado los datos modificados.

### 10.2 Política de Versionado de Esquemas
Los esquemas de telemetría siguen **Versionado Semántico (SemVer)** bajo el formato `MAJOR.MINOR.PATCH`:
1. **PATCH (`x.x.+1`):** Correcciones en descripciones de campos, documentación o adición de metadatos no vinculantes en el esquema.
2. **MINOR (`x.+1.0`):** Adición de nuevas propiedades opcionales en el allowlist de `properties`. Los consumidores existentes deben ignorar propiedades adicionales desconocidas si no las requieren, pero los productores deben apegarse al contrato.
3. **MAJOR (`+1.0.0`):** Cambios incompatibles hacia atrás: eliminación de campos, renombrado de propiedades, cambio de tipos de datos o modificación de obligatoriedad.
4. **Política de Transición y Deprecación:** Cualquier cambio de versión mayor (`MAJOR`) requiere un período de compatibilidad de al menos **90 días**, durante el cual la infraestructura de ingestión debe procesar de forma dual ambas versiones mediante adaptadores antes de apagar la versión obsoleta.

---

## 11. Allowlist de Propiedades

Cada evento dispone de una **allowlist explícita** donde se prohíbe terminantemente la inclusión de campos no definidos (`additionalProperties: false`).

| Evento (`event_type`) | Propiedad | Tipo | Obligatoria | Valores Permitidos / Formato | PII | Regla de Sanitización / Exclusión |
| :--- | :--- | :--- | :---: | :--- | :---: | :--- |
| `inbound_order_created` | `order_id` | `string` | Sí | UUID v4 | No | ID sintético de base de datos. |
| | `local_id` | `string` | Sí | Min 1 char (e.g. `MED-001`) | No | Clave natural de sede. |
| | `ingredient_id` | `string` | Sí | UUID v4 | No | ID sintético de catálogo. |
| | `ingredient_sku` | `string` | Sí | Min 1 char (e.g. `ING-001`) | No | Código SKU interno. |
| | `quantity` | `number` | Sí | $> 0$ | No | Cantidad numérica. |
| | `unit_of_measure` | `string` | Sí | `kg`, `litros`, `unidades` | No | Unidad normalizada. |
| | `previous_stock` | `number` | Sí | Numérico | No | Saldo antes de entrada. |
| | `resulting_stock` | `number` | Sí | Numérico | No | Saldo después de entrada. |
| `outbound_order_created` | `order_id` | `string` | Sí | UUID v4 | No | ID sintético de salida. |
| | `local_id` | `string` | Sí | Min 1 char (e.g. `MED-001`) | No | Clave natural de sede. |
| | `ingredient_id` | `string` | Sí | UUID v4 | No | ID sintético de catálogo. |
| | `ingredient_sku` | `string` | Sí | Min 1 char (e.g. `ING-001`) | No | Código SKU interno. |
| | `quantity` | `number` | Sí | $> 0$ | No | Cantidad numérica. |
| | `unit_of_measure` | `string` | Sí | `kg`, `litros`, `unidades` | No | Unidad normalizada. |
| | `previous_stock` | `number` | Sí | Numérico | No | Saldo antes de salida. |
| | `resulting_stock` | `number` | Sí | $\ge 0$ | No | Saldo remanente no negativo. |
| `stock_threshold_triggered` | `local_id` | `string` | Sí | Min 1 char | No | Clave de sede. |
| | `ingredient_id` | `string` | Sí | UUID v4 | No | ID de ingrediente. |
| | `ingredient_sku` | `string` | Sí | Min 1 char | No | SKU de ingrediente. |
| | `current_stock` | `number` | Sí | Numérico | No | Saldo actual. |
| | `minimum_stock` | `number` | Sí | $\ge 0$ | No | Umbral configurado. |
| | `deficit` | `number` | Sí | $\ge 0$ | No | Brecha de restitución. |
| | `unit_of_measure` | `string` | Sí | Min 1 char | No | Unidad de medida. |
| | `severity` | `string` | Sí | `critical_depletion`, `minimum_reached` | No | Enum estandarizado. |
| `outbound_insufficient_stock_attempted` | `local_id` | `string` | Sí | Min 1 char | No | Clave de sede. |
| | `ingredient_id` | `string` | Sí | UUID v4 | No | ID de ingrediente. |
| | `ingredient_sku` | `string` | Sí | Min 1 char | No | SKU de ingrediente. |
| | `requested_quantity` | `number` | Sí | $> 0$ | No | Cantidad intentada. |
| | `available_stock` | `number` | Sí | Numérico | No | Saldo disponible al intento. |
| | `unit_of_measure` | `string` | Sí | Min 1 char | No | Unidad de medida. |
| | `rejection_source` | `string` | Sí | `client_form_guard`, `backend_transaction_lock` | No | Punto de intercepción. |
| `direct_stock_edit_rejected` | `target_resource` | `string` | Sí | Min 1 char | No | Recurso intentado. |
| | `attempted_operation` | `string` | Sí | `PUT`, `PATCH`, `DIRECT_UPDATE` | No | Método HTTP/Operación. |
| | `rejection_reason` | `string` | Sí | Min 1 char | No | Justificación arquitectónica. |
| | `local_id` | `string` | Sí | Min 1 char | No | Sede contextualizada. |
| `inventory_catalog_viewed` | `local_id` | `string` | Sí | Min 1 char | No | Sede visualizada. |
| | `total_items_rendered` | `integer` | Sí | $\ge 0$ | No | Conteo de catálogo. |
| | `low_stock_items_count` | `integer` | Sí | $\ge 0$ | No | Conteo de alertas. |
| | `depleted_items_count` | `integer` | Sí | $\ge 0$ | No | Conteo de agotados. |
| `ingredient_detail_queried` | `local_id` | `string` | Sí | Min 1 char | No | Sede consultada. |
| | `ingredient_id` | `string` | Sí | UUID v4 | No | ID de ingrediente. |
| | `ingredient_sku` | `string` | Sí | Min 1 char | No | SKU de ingrediente. |
| | `current_stock` | `number` | Sí | Numérico | No | Saldo devuelto. |
| | `unit_of_measure` | `string` | Sí | Min 1 char | No | Unidad de medida. |
| `inventory_filter_applied` | `local_id` | `string` | Sí | Min 1 char | No | Sede activa. |
| | `category_filter` | `string` | Sí | Categoría o `ALL` | No | Filtro tipificado. |
| | `search_term_length` | `integer` | Sí | $\ge 0$ | No | Longitud; texto excluido por PII. |
| | `results_count` | `integer` | Sí | $\ge 0$ | No | Conteo de resultados. |
| `purchase_order_suggested` | `suggestion_id` | `string` | Sí | UUID v4 | No | ID de propuesta. |
| | `local_id` | `string` | Sí | Min 1 char | No | Sede destino. |
| | `supplier_id` | `string` | Sí | Min 1 char | No | ID de proveedor. |
| | `items_count` | `integer` | Sí | $\ge 1$ | No | Número de líneas. |
| | `total_estimated_amount` | `number` | Sí | $\ge 0$ | No | Importe estimado. |
| | `currency` | `string` | Sí | `COP`, `USD` | No | Moneda de sede. |
| | `trigger_reason` | `string` | Sí | `scheduled_replenishment`, `stockout_prevention`, `manual_generation` | No | Causa tipificada. |
| `purchase_order_approved` | `order_id` | `string` | Sí | UUID v4 | No | ID de orden. |
| | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `supplier_id` | `string` | Sí | Min 1 char | No | ID de proveedor. |
| | `total_approved_amount` | `number` | Sí | $\ge 0$ | No | Importe aprobado. |
| | `currency` | `string` | Sí | `COP`, `USD` | No | Moneda. |
| | `approver_role` | `string` | Sí | Rol de usuario | No | Rol (sin PII personal). |
| | `approval_latency_seconds` | `number` | Sí | $\ge 0$ | No | Latencia de aprobación. |
| `purchase_order_dispatched` | `order_id` | `string` | Sí | UUID v4 | No | ID de orden. |
| | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `supplier_id` | `string` | Sí | Min 1 char | No | ID de proveedor. |
| | `dispatch_channel` | `string` | Sí | `email`, `edi_api`, `portal` | No | Canal técnico. |
| | `estimated_delivery_date` | `string` | Sí | `YYYY-MM-DD` | No | Fecha estimada. |
| `purchase_order_received` | `order_id` | `string` | Sí | UUID v4 | No | ID de orden. |
| | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `supplier_id` | `string` | Sí | Min 1 char | No | ID de proveedor. |
| | `fulfillment_status` | `string` | Sí | `complete`, `partial`, `discrepant` | No | Cumplimiento tipificado. |
| | `lead_time_hours` | `number` | Sí | $\ge 0$ | No | Lead time en horas. |
| `purchase_order_rejected` | `order_id` | `string` | Sí | UUID v4 | No | ID de orden. |
| | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `supplier_id` | `string` | Sí | Min 1 char | No | ID de proveedor. |
| | `rejection_reason_code` | `string` | Sí | `budget_limit_exceeded`, `duplicate_order`, `supplier_unavailable`, `manual_cancellation` | No | Código controlado. |
| `supplier_price_variance_detected` | `supplier_id` | `string` | Sí | Min 1 char | No | ID de proveedor. |
| | `ingredient_id` | `string` | Sí | UUID v4 | No | ID de ingrediente. |
| | `ingredient_sku` | `string` | Sí | Min 1 char | No | SKU de ingrediente. |
| | `contracted_unit_price` | `number` | Sí | $> 0$ | No | Precio pactado. |
| | `invoiced_unit_price` | `number` | Sí | $> 0$ | No | Precio facturado. |
| | `variance_percentage` | `number` | Sí | Numérico | No | Desviación porcentual. |
| | `currency` | `string` | Sí | `COP`, `USD` | No | Moneda. |
| `consolidated_procurement_report_generated` | `reporting_period` | `string` | Sí | `YYYY-WXX` (e.g. `2026-W38`) | No | Semana ISO. |
| | `total_spend_cop` | `number` | Sí | $\ge 0$ | No | Gasto consolidado COP. |
| | `total_spend_usd` | `number` | Sí | $\ge 0$ | No | Gasto consolidado USD. |
| | `total_orders_count` | `integer` | Sí | $\ge 0$ | No | Conteo de órdenes. |
| | `active_suppliers_count` | `integer` | Sí | $\ge 0$ | No | Proveedores involucrados. |
| `daily_sales_recorded` | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `business_date` | `string` | Sí | `YYYY-MM-DD` | No | Fecha de turno. |
| | `total_sales_amount` | `number` | Sí | $\ge 0$ | No | Venta bruta. |
| | `currency` | `string` | Sí | `COP`, `USD` | No | Moneda local. |
| | `total_covers` | `integer` | Sí | $\ge 0$ | No | Comensales. |
| | `average_ticket` | `number` | Sí | $\ge 0$ | No | Ticket promedio. |
| | `lines_count` | `integer` | Sí | $\ge 0$ | No | Conteo de platos. |
| `pos_order_completed` | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `order_id` | `string` | Sí | Min 1 char | No | ID ticket POS. |
| | `total_amount` | `number` | Sí | $\ge 0$ | No | Total comanda. |
| | `currency` | `string` | Sí | `COP`, `USD` | No | Moneda. |
| | `covers` | `integer` | Sí | $\ge 1$ | No | Personas en ticket. |
| | `items_count` | `integer` | Sí | $\ge 1$ | No | Cantidad artículos. |
| `location_zero_sales_alert_triggered` | `local_id` | `string` | Sí | Min 1 char | No | Sede inactiva. |
| | `operating_minutes_without_sales` | `integer` | Sí | $\ge 15$ | No | Minutos inactivo. |
| | `operating_hour` | `integer` | Sí | 0 a 23 | No | Hora local del día. |
| | `expected_minimum_covers` | `integer` | Sí | $\ge 0$ | No | Demanda esperada. |
| `pos_heartbeat_recorded` | `local_id` | `string` | Sí | Min 1 char | No | Sede. |
| | `terminal_id` | `string` | Sí | Min 1 char | No | ID hardware caja. |
| | `connectivity_status` | `string` | Sí | `online`, `degraded`, `offline_sync` | No | Estado de red. |
| `user_logged_in` | `auth_provider` | `string` | Sí | `local_password`, `jwt_refresh` | No | Método de login. |
| | `user_role` | `string` | Sí | Rol de usuario | No | Rol funcional. |
| | `assigned_local_id` | `string` | Sí | Sede o `ALL` | No | Sede asignada. |
| `user_login_failed` | `failure_reason` | `string` | Sí | `invalid_credentials`, `account_locked`, `inactive_user`, `rate_limited` | No | Motivo controlado. |
| | `attempt_counter` | `integer` | Sí | $\ge 1$ | No | Conteo de intento. |
| `session_expired` | `expiry_reason` | `string` | Sí | `token_jwt_expired`, `idle_timeout`, `forced_logout` | No | Causa de expiración. |
| | `session_duration_seconds` | `integer` | Sí | $\ge 0$ | No | Duración de sesión. |
| `permission_denied` | `required_role` | `string` | Sí | Min 1 char | No | Rol exigido. |
| | `user_role` | `string` | Sí | Min 1 char | No | Rol del solicitante. |
| | `target_endpoint` | `string` | Sí | Ruta normalizada | No | Recurso protegido. |
| | `http_method` | `string` | Sí | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | No | Método HTTP. |
| `password_reset_requested` | `delivery_channel` | `string` | Sí | `email` | No | Canal de entrega. |
| | `request_outcome` | `string` | Sí | `dispatched`, `suppressed_unknown_account` | No | Resultado genérico sin fugar existencia de cuenta. |
| `api_latency_recorded` | `route_path` | `string` | Sí | Min 1 char (e.g. `/inventory/orders`) | No | Ruta parametrizada. |
| | `http_method` | `string` | Sí | `GET`, `POST`, `PUT`, `PATCH`, `DELETE` | No | Método HTTP. |
| | `status_code` | `integer` | Sí | 100 a 599 | No | Código HTTP. |
| | `duration_ms` | `number` | Sí | $\ge 0$ | No | Duración en ms. |
| | `db_query_count` | `integer` | Sí | $\ge 0$ | No | Consultas SQL. |
| `client_web_vitals_recorded` | `page_route` | `string` | Sí | Ruta Next.js | No | Ruta en frontend. |
| | `metric_name` | `string` | Sí | `LCP`, `FID`, `CLS`, `INP`, `TTFB` | No | Métrica Web Vitals. |
| | `metric_value` | `number` | Sí | $\ge 0$ | No | Valor numérico. |
| | `rating` | `string` | Sí | `good`, `needs_improvement`, `poor` | No | Calificación oficial. |
| `db_query_slow_detected` | `query_type` | `string` | Sí | `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `AGGREGATE` | No | Operación SQL. |
| | `table_name` | `string` | Sí | Min 1 char | No | Tabla afectada. |
| | `execution_time_ms` | `number` | Sí | $\ge 0$ | No | Tiempo en ms. |
| | `threshold_ms` | `number` | Sí | $\ge 0$ | No | Umbral superado. |
| `form_validation_failed` | `form_id` | `string` | Sí | `inbound_order_form`, `outbound_order_form`, `ingredient_create_form`, `supplier_form` | No | Formulario. |
| | `field_name` | `string` | Sí | Min 1 char | No | Nombre del input. |
| | `error_rule` | `string` | Sí | Min 1 char | No | Regla quebrada. |
| `system_exception_captured` | `exception_class` | `string` | Sí | Min 1 char | No | Clase de excepción. |
| | `error_code` | `string` | Sí | Min 1 char | No | Código estandarizado. |
| | `origin_service` | `string` | Sí | Min 1 char | No | Servicio emisor. |
| `external_integration_failed` | `integration_target` | `string` | Sí | `resend_email`, `pos_gateway`, `whatsapp_api` | No | Destino externo. |
| | `error_code` | `string` | Sí | Min 1 char | No | Código de error. |
| | `retry_attempt` | `integer` | Sí | $\ge 0$ | No | Conteo de reintento. |
| `backoffice_page_viewed` | `previous_route` | `string` | Sí | Ruta o `DIRECT_ENTRY` | No | Origen navegación. |
| | `current_route` | `string` | Sí | Min 1 char | No | Destino navegación. |
| | `navigation_duration_ms` | `number` | Sí | $\ge 0$ | No | Tiempo de estancia. |
| `form_abandoned` | `form_id` | `string` | Sí | `inbound_order_form`, `outbound_order_form`, `ingredient_create_form` | No | Formulario. |
| | `fields_filled_count` | `integer` | Sí | $\ge 1$ | No | Conteo de campos. |
| | `time_spent_seconds` | `integer` | Sí | $\ge 0$ | No | Tiempo interactuando. |

---

## 12. Privacidad, PII y Sanitización

### 12.1 Lista Negra Radical (Zero PII Policy)
Queda estrictamente prohibido capturar, almacenar o transmitir en cualquier payload telemétrico los siguientes elementos:
- Contraseñas en texto plano o hashes.
- Tokens JWT de acceso o actualización (`access_token`, `refresh_token`).
- Secretos, API keys, credenciales de base de datos o variables `.env`.
- Cookies de navegación o identificadores de sesión de terceros.
- Cabeceras `Authorization` o contenido de cabeceras HTTP que transporten credenciales.
- Cuerpos completos (`payload bodies`) de peticiones o respuestas HTTP.
- Nombres completos de personas, correos electrónicos o números telefónicos en texto plano.
- Direcciones físicas de residencias de colaboradores o clientes.
- Texto libre de notas, comentarios de pedidos o descripciones abiertas.
- Trazas de pila completas (`stack traces`) que revelen rutas internas del servidor o fragmentos de código.
- Contenido binario o textual de archivos adjuntos.
- Datos de tarjetas de pago, números de cuenta bancaria o información financiera de clientes.
- Parámetros en query strings que puedan alojar identificadores personales.

### 12.2 Tratamiento Específico de Identificadores y Datos Sensibles
1. **`userId`:** Se representa exclusivamente mediante un UUID v4 sintético seudonimizado (`user_uuid` generado en backend). Queda prohibido el uso de direcciones de correo electrónico (`email`) o nombres de usuario (`username`). Un evento emitido sin sesión de usuario (e.g. crons automáticos) debe establecer `userId: null`.
2. **`sessionId`:** UUID efímero generado por el frontend durante el inicio de sesión. No debe contener ninguna porción del token JWT ni relacionarse matemáticamente con el secreto del servidor.
3. **Direcciones IP:** Se excluyen de la carga telemétrica estándar. En caso de requerirse métricas de conectividad en el borde de la red (edge proxies), la dirección IP debe truncarse a nivel de red (máscara `/24` para IPv4 o `/48` para IPv6) o descartarse inmediatamente tras resolver el país y la ciudad.
4. **Mensajes de error y excepciones:** Se normalizan en códigos de error estandarizados (`error_code`, e.g. `INSUFFICIENT_STOCK_EXCEPTION`, `CATALOG_UNAVAILABLE`) y nombres de clase. Nunca se incluyen cadenas de error generadas por la base de datos que revelen tablas o datos de registros.
5. **IDs de entidades (Órdenes, Ingredientes, Proveedores y Locales):** Se utilizan exclusivamente claves sintéticas estructuradas (`MED-001`, `ING-001`) o UUIDs v4 de base de datos.
6. **Términos de búsqueda y campos de texto:** En búsquedas de catálogo y filtros, **nunca** se captura la cadena de texto ingresada por el usuario (ante el riesgo de que escriba un nombre o teléfono). Se registra exclusivamente la longitud del término (`search_term_length`) y la categoría seleccionada.

---

## 13. Estrategia Batch frente a Stream y Hybrid

La clasificación de transporte responde a criterios estrictamente operativos de necesidad de negocio, evitando preferencias técnicas arbitrarias.

| Tipo de Entrega | Criterio de Selección Operativo | Consecuencia si se Retrasa |
| :--- | :--- | :--- |
| **`stream`** | Suceso que requiere intervención operativa inmediata en restaurante (< 30 segundos) o alerta crítica de seguridad. | Quiebre de stock en cocina durante el servicio; local cerrado o incomunicado sin detección; vulneración de seguridad desatendida. |
| **`batch`** | Métricas históricas, indicadores consolidados de gestión, análisis de usabilidad y rendimiento agregado donde prima la eficiencia de red y costo. | Ningún impacto en la operación en vivo; el reporte o análisis se actualiza en el siguiente ciclo planificado sin afectar al cliente. |
| **`hybrid`** | Doble vía: flujo en tiempo real para actualización de saldos y alertas operativas, combinado con consolidación posterior en lote para auditoría y contabilidad. | Se preserva la agilidad inmediata en sede, mientras que la contabilidad y conciliación fiscal se procesan en ventanas nocturnas de bajo costo. |

### 13.1 Clasificación Operativa por Categoría de Evento

| Categoría | Eventos | Modo | Latencia Tolerable | Consumidor Esperado | Decisión Habilitada | Coste / Complejidad |
| :--- | :--- | :---: | :---: | :--- | :--- | :--- |
| **Inventario Crítico** | `stock_threshold_triggered`<br>`outbound_insufficient_stock_attempted`<br>`direct_stock_edit_rejected` | `stream` | < 5 s | Motor de Alertas Push / Supervisores de Sede | Reabastecimiento de emergencia; bloqueo de salidas indebidas; auditoría inmediata. | Medio: Requiere canal WebSocket / PubSub con bajo retardo. |
| **Kardex Operativo** | `inbound_order_created`<br>`outbound_order_created` | `hybrid` | < 3 s (stream)<br>24 h (batch) | Visualizador de Stock en Cocina / ERP Contable | Mostrar saldo inmediato al cocinero y conciliar inventario fiscal al cierre. | Medio-Alto: Publicación dual (inmediata en bus + outbox transaccional). |
| **Catálogo y Consultas** | `inventory_catalog_viewed`<br>`ingredient_detail_queried`<br>`inventory_filter_applied` | `batch` | 60 s | Analítica de Uso de Backoffice | Optimización de filtros y layout de tablas de insumos. | Muy Bajo: Bufferizado en memoria del navegador antes de enviar. |
| **Aprovisionamiento** | `purchase_order_approved`<br>`purchase_order_dispatched`<br>`supplier_price_variance_detected` | `stream` | < 15 s | Pasarela de Envíos a Proveedores / Lucía Fernández | Despacho ágil de compras y congelamiento de pagos ante sobreprecios. | Medio: Crítico para cumplir SLAs de entrega de proveedores. |
| **Planificación Compras** | `purchase_order_suggested`<br>`purchase_order_received`<br>`purchase_order_rejected`<br>`consolidated_procurement_report_generated` | `hybrid` / `batch` | 1 h a 24 h | Pipeline de Reentrenamiento IA / Reporte Ejecutivo Semanal | Calibración de modelos de demanda y negociación de volumen por Lucía. | Bajo: Tareas en segundo plano ejecutadas en horas valle. |
| **Operaciones de Ventas** | `pos_order_completed`<br>`location_zero_sales_alert_triggered`<br>`pos_heartbeat_recorded` | `stream` | < 2 s a 30 s | Explosión de Recetas en Cocina / Alerta a Felipe Guerrero | Descontar insumos en tiempo real; acudir al local ante corte de POS. | Alto: Alto volumen transaccional en horas de almuerzo y cena. |
| **Cierre Contable** | `daily_sales_recorded` | `batch` | 2 h | Data Warehouse / Dashboard CEO (Mariana Restrepo) | Consolidación de ingresos multi-divisa y rentabilidad semanal. | Bajo: Ingestión nocturna de 14 registros diarios. |
| **Seguridad y Acceso** | `user_login_failed`<br>`permission_denied`<br>`system_exception_captured`<br>`external_integration_failed` | `stream` | < 5 s | Monitor de Seguridad / Guardia Técnica DevOps | Bloqueo de ataques de fuerza bruta; resolución de errores 500. | Medio: Flujo de baja frecuencia pero alta prioridad operativa. |
| **Sesión y UX** | `user_logged_in`<br>`session_expired`<br>`password_reset_requested`<br>`api_latency_recorded`<br>`client_web_vitals_recorded`<br>`db_query_slow_detected`<br>`form_validation_failed`<br>`backoffice_page_viewed`<br>`form_abandoned` | `batch` / `hybrid` | 60 s a 5 min | Tableros APM / Analítica de Producto y Formularios | Optimización de tiempos de respuesta, reducción de fricción en formularios. | Bajo: Buffer local y compresión gzip en envíos periódicos. |

---

## 14. Correlación Frontend–Backend

Para reconstruir la causalidad completa de un suceso a lo largo de los diferentes niveles de la arquitectura, se implementa una estrategia estricta de correlación distribuida basada en `requestId`:

### 14.1 Propagación Distribuida
1. **Inicio en Frontend (Next.js):**
   - Cuando el usuario interactúa con la interfaz (e.g. clic en *Registrar Salida de Stock*), el cliente HTTP (`src/lib/inventory.ts`) genera un UUID v4 identificador de correlación y lo inyecta en la cabecera estándar `X-Request-ID`.
   - Si el navegador soporta el estándar W3C Distributed Tracing, se inyecta adicionalmente la cabecera `traceparent`.
2. **Propagación en Backend (FastAPI):**
   - Un middleware de correlación en `services/api/app/main.py` intercepta la petición HTTP:
     - Si la cabecera `X-Request-ID` está presente, valida su formato y la asocia al contexto asíncrono de la petición (`contextvars`).
     - Si la cabecera no está presente (e.g. llamada directa de un script), genera un nuevo UUID v4.
   - La cabecera `X-Request-ID` se devuelve obligatoriamente en todas las respuestas HTTP para permitir que el cliente correlacione errores de consola.
3. **Persistencia e Ingestión:**
   - Cualquier evento telemétrico emitido durante el procesamiento de dicha solicitud hereda idéntico `requestId` en su Event Envelope.
   - Cuando un evento de dominio se persiste en la base de datos (e.g. tabla `telemetry_outbox`), el `requestId` viaja como atributo de correlación hacia el bus de eventos y pipelines posteriores.

```
[Usuario en Backoffice] 
       │ Clic en "Registrar Salida" (Genera requestId: e2a74c10...)
       ▼
[Cliente HTTP / Next.js] ── Headers: X-Request-ID: e2a74c10... ──► [FastAPI Middleware]
                                                                        │ Inyecta en Request Scope
                                                                        ▼
                                                             [Inventory Service / SQLModel]
                                                                        │ Ejecuta transacción
                                                                        ▼
                                                             [Emisión Telemétrica]
                                                             Envelope.requestId = e2a74c10...
                                                                        │
                                                                        ▼
                                                             [Log Central / Event Bus]
```

---

## 15. Retry, Throttle, Debounce y Deduplicación

### 15.1 Debounce para Interacciones de Usuario
- **Ámbito:** Búsquedas en catálogo, inputs de filtrado y redimensionamiento de tablas en `uis/backoffice`.
- **Estrategia:** Se aplica un temporizador de debounce de **500 ms**. Si el usuario teclea múltiples caracteres de forma continua en el buscador de inventario, se cancela el temporizador anterior y únicamente se emite el evento `inventory_filter_applied` cuando la entrada permanece inactiva durante medio segundo. Esto elimina hasta el 92% del volumen telemétrico espurio.

### 15.2 Throttle y Cooldown para Alertas Repetitivas
- **Ámbito:** `stock_threshold_triggered` y `location_zero_sales_alert_triggered`.
- **Regla de Cooldown:** Cuando un ingrediente en una sede cruza su stock mínimo y emite `stock_threshold_triggered`, el emisor registra una clave en memoria/Redis `throttle:stock:{local_id}:{ingredient_id}` con un TTL de **30 minutos**.
- **Excepción de Escalamiento:** Si el saldo disponible pasa de estar en *stock bajo* ($> 0$ y $\le \text{mínimo}$) a *agotamiento total* ($\le 0$), se omite el cooldown y se emite de inmediato un nuevo evento con `severity: critical_depletion`.
- **Alerta de Cero Ventas:** `location_zero_sales_alert_triggered` aplica una ventana de throttle de **60 minutos** por sede para evitar saturar al Director de Operaciones mientras se atiende la contingencia reportada.

### 15.3 Reintentos con Backoff Exponencial y Jitter
- **Ámbito:** Fallos transitorios de red en el envío de eventos desde el cliente o workers hacia el recolector.
- **Fórmula de Retardo:**
  $$t_{\text{retry}} = \min\left(t_{\max},\; t_{\text{base}} \times 2^{\text{intento}}\right) \pm \text{jitter}$$
  - $t_{\text{base}} = 500\text{ ms}$
  - $t_{\max} = 30\text{ segundos}$
  - $\text{jitter} = \text{valor aleatorio entre } 0 \text{ y } 250\text{ ms}$
  - $\text{Máximo de reintentos} = 4$
- Si tras 4 intentos la entrega falla, los eventos batch se almacenan temporalmente en `IndexedDB` (en navegador) o en un buffer en disco (en servidor) con límite de tamaño FIFO (máximo 5 MB o 1000 eventos), descartando los más antiguos no críticos si se llena la memoria.

### 15.4 Deduplicación e Idempotencia Mediante `eventId`
- **Garantía del Productor:** Cada evento genera su propio `eventId` (UUID v4) en el momento exacto en que ocurre el hecho, antes de iniciar la transmisión de red.
- **Idempotencia en Ingestión:**
  - La capa de recepción de telemetría mantiene una caché distribuida en Redis con las claves `dedup:{eventId}` y un tiempo de expiración (TTL) de **24 horas**.
  - Si un reintento de red reenvía un evento con un `eventId` ya procesado, la API responde de inmediato con `HTTP 200 OK` (acuse de recibo idempotente), pero descarta el mensaje para que no ingrese a las colas analíticas ni distorsione los agregados.
- **Tratamiento de Eventos Fuera de Orden:** Las canalizaciones de agregación utilizan marcas de tiempo de suceso (`timestamp`) contenidas en el envelope en lugar de la hora de llegada al servidor. Las ventanas de procesamiento en streaming implementan una tolerancia de desfase por eventos tardíos (*watermark*) de **15 minutos**.

### 15.5 Principio de No Bloqueo Operativo (Circuit Breaker y Outbox)
- **Aislamiento Estricto:** La telemetría **nunca** debe bloquear, ralentizar ni abortar una operación crítica de inventario o cocina.
- **En Backend:** Las emisiones telemétricas se ejecutan de forma asíncrona fuera del ciclo de la transacción principal de PostgreSQL, o se escriben de manera atómica en la misma transacción mediante una tabla local `telemetry_outbox` (garantizando consistencia sin depender de la disponibilidad del bus de eventos). Si el recolector de eventos se encuentra caído, la transacción de inventario se completa exitosamente.
- **En Frontend:** Las llamadas de telemetría utilizan `navigator.sendBeacon` o peticiones `fetch` desacopladas (`keepalive: true`) sin esperar la respuesta (`fire-and-forget`) ni mostrar advertencias que confundan al usuario.

---

## 16. Riesgos y Exclusiones

| Riesgo Identificado | Impacto Operativo | Estrategia de Mitigación en el Diseño |
| :--- | :--- | :--- |
| **Pérdida de conectividad en restaurante** | Imposibilidad de transmitir telemetría POS o de cocina en tiempo real durante horas de alta demanda. | El terminal POS almacena eventos localmente en cola SQLite y emite `pos_heartbeat_recorded` con estado `offline_sync`. Al restablecerse la red, los eventos se sincronizan en ráfaga con su `timestamp` original. |
| **Tormenta de alertas por umbrales** | Saturación de mensajes de alerta en WhatsApp a supervisores cuando múltiples insumos bajan de nivel simultáneamente. | Cooldown estricto de 30 minutos por ingrediente y agrupación inteligente en mensajes consolidados cada 15 minutos en lugar de alertas individuales repetidas. |
| **Sobrecarga de la base de datos PostgreSQL** | Caída de rendimiento si se ejecutan consultas telemétricas pesadas sobre las tablas de movimientos transaccionales. | Separación arquitectónica: la base de datos operacional únicamente persiste movimientos ($O(1)$ con bloqueo de fila). Los eventos telemétricos viajan a un bus analítico separado sin competir por CPU transaccional. |
| **Fuga accidental de datos personales (PII)** | Violación de normativas de privacidad (Habeas Data Colombia / leyes de Florida) por captura de nombres o emails. | Política Zero-PII enforceable mediante validación de esquema Draft 2020-12 con `additionalProperties: false`. Los analizadores estáticos bloquean campos libres de texto. |
| **Desincronización de relojes (Clock Skew)** | Inconsistencias temporales si los terminales de punto de venta poseen horas locales erróneas. | Validación en ingestión: todo evento cuyo `timestamp` difiera en más de $\pm 10$ minutos respecto a la hora UTC del servidor recolector se etiqueta con una advertencia de desvío temporal y se registra el `server_received_at`. |

---

## 17. Eventos Considerados y Descartados

Durante el análisis arquitectónico se evaluaron y descartaron conscientemente los siguientes 5 eventos telemétricos por razones de costo, ruido, rendimiento y privacidad:

1. **`raw_keystroke_logged` (Pulsación de Teclas en Búsqueda):**
   - *Considerado para:* Monitorear en tiempo real la velocidad de escritura de los supervisores en los filtros.
   - *Razón de exclusión:* Descartado radicalmente por sobrecoste masivo de ancho de banda, ruido irrelevante y grave riesgo de captura accidental de PII (e.g. si un usuario escribe un número telefónico por error). En su lugar se adopta `inventory_filter_applied` con debounce y captura exclusiva de la longitud del texto (`search_term_length`).
2. **`mouse_movement_heatmap_tracked` (Mapa de Calor de Cursor):**
   - *Considerado para:* Registrar coordenadas $(x, y)$ del ratón en las pantallas del backoffice.
   - *Razón de exclusión:* Inadecuado para herramientas operativas internas de gestión de cocina y bodega. Representa un consumo excesivo de batería en dispositivos móviles y congestión de red sin aportar ningún valor para las decisiones de reabastecimiento ni reducción de quiebres de stock.
3. **`pos_terminal_button_clicked` (Clic Individual en Botones del TPV):**
   - *Considerado para:* Medir cada interacción física en el software de punto de venta.
   - *Razón de exclusión:* Generaría millones de eventos por servicio sin utilidad analítica. El evento de negocio relevante es `pos_order_completed`, el cual ya consolida los platillos y totales de la transacción.
4. **`auth_token_refreshed` (Renovación Silenciosa de Token JWT):**
   - *Considerado para:* Emitir un evento cada vez que el middleware renueva un token en segundo plano.
   - *Razón de exclusión:* Es un detalle de implementación de bajo nivel que genera spam telemétrico de alta frecuencia sin implicación de negocio. La trazabilidad de seguridad se satisface de forma limpia mediante `user_logged_in` y `session_expired`.
5. **`database_connection_acquired` (Adquisición de Conexión en Pool SQL):**
   - *Considerado para:* Monitorear la apertura de conexiones SQLAlchemy.
   - *Razón de exclusión:* Confunde la telemetría de eventos de producto con las métricas de infraestructura (APM/Prometheus). Pertenece a métricas de instrumentación de servidor (gauges de conexión de pool), no al bus de eventos de telemetría de dominio.

---

## 18. Guía Precisa de Futura Instrumentación

Para asegurar que cualquier ingeniero de software pueda instrumentar el sistema sin solicitar aclaraciones adicionales, se detallan los puntos exactos de inyección lógica en el código del monorepo:

### 18.1 Backend FastAPI (`services/api`)

#### Punto 1: Creación de Entrada de Inventario (Inbound)
- **Ubicación:** `services/api/app/domains/operations/inventory/service.py` en la función `create_inbound_order()`.
- **Momento:** Inmediatamente después de `repository.create_inbound_entry()` y antes del `return OrderResponse`.
- **Evento:** `inbound_order_created`.
- **Datos a inyectar:** `order_id` (de `entry.id`), `local_id`, `ingredient_id`, `ingredient_sku`, `quantity`, `unit_of_measure`, `previous_stock` (obtenido en el repositorio antes de la inserción) y `resulting_stock` (`previous_stock + quantity`).

#### Punto 2: Creación de Salida de Inventario (Outbound) y Alerta de Umbral
- **Ubicación:** `services/api/app/domains/operations/inventory/service.py` en la función `create_outbound_order()`.
- **Momento:**
  - **Rama de Error:** En el bloque `except repository.InsufficientStockError as exc:`, antes de lanzar el `HTTPException(400)`, emitir `outbound_insufficient_stock_attempted` con `rejection_source: "backend_transaction_lock"`.
  - **Rama Exitosa:** Inmediatamente después de confirmarse la transacción en PostgreSQL (`repository.create_outbound_exit_with_lock()`), emitir `outbound_order_created`.
  - **Evaluación de Alerta:** Si `resulting_stock <= ing.minimum_stock`, emitir inmediatamente en stream `stock_threshold_triggered` evaluando si el saldo es $\le 0$ (`critical_depletion`) o $\le \text{mínimo}$ (`minimum_reached`).

#### Punto 3: Middleware de Latencia y Correlación HTTP
- **Ubicación:** `services/api/app/main.py` mediante un middleware de aplicación `@app.middleware("http")`.
- **Momento:** Al recibir la petición, extraer o generar `X-Request-ID`. Al finalizar `await call_next(request)`, calcular `duration_ms = (time.perf_counter() - start_time) * 1000` y encolar `api_latency_recorded`.

#### Punto 4: Autenticación y Manejo de Errores Globales
- **Ubicación:**
  - `services/api/app/domains/auth/router.py`: Tras generar el token JWT en `login()`, emitir `user_logged_in`. En `authenticate_user()`, si las credenciales fallan, emitir `user_login_failed`.
  - `services/api/app/domains/auth/dependencies.py`: En `get_current_user()`, si el rol es insuficiente, emitir `permission_denied`.
  - `services/api/app/main.py`: En el exception handler global para `Exception`, emitir `system_exception_captured`.

---

### 18.2 Frontend Backoffice (`uis/backoffice`)

#### Punto 5: Formulario de Salida de Stock (`OutboundOrderForm`)
- **Ubicación:** `uis/backoffice/src/components/inventory/outbound-order-form.tsx`.
- **Momento:**
  - En la condición preventiva `isOverStock` (cuando el usuario ingresa una cantidad superior al saldo disponible y el botón se desactiva), emitir `outbound_insufficient_stock_attempted` con `rejection_source: "client_form_guard"`.
  - En el `handleSubmit` si la API devuelve error 400 (`InventoryApiError`).
  - En el evento de limpieza o navegación sin guardar si `quantity !== ''`, emitir `form_abandoned`.

#### Punto 6: Visualización de Catálogo y Filtros
- **Ubicación:** `uis/backoffice/src/components/inventory/products-table.tsx`.
- **Momento:**
  - Tras resolver exitosamente `inventoryApi.listProducts(selectedRestaurant)`, emitir `inventory_catalog_viewed` calculando en memoria los conteos de `low_stock_items_count` y `depleted_items_count`.
  - En el selector de sede o inputs de búsqueda, aplicar debounce de 500 ms y emitir `inventory_filter_applied`.

#### Punto 7: Core Web Vitals y Navegación
- **Ubicación:** `uis/backoffice/src/app/layout.tsx` y componentes de navegación.
- **Momento:**
  - Utilizar el hook nativo de Next.js `useReportWebVitals` para capturar `LCP`, `CLS`, `INP` y emitir `client_web_vitals_recorded`.
  - En el componente `BackofficeHeader` o listener de ruta, emitir `backoffice_page_viewed` al completarse la transición de página.

---

## 19. Validación y Criterios de Aceptación

### 19.1 Evidencias y Comandos de Validación Ejecutados
1. **Validación Formal de Esquemas JSON:**
   - Se validó `docs/telemetry/event-schemas.json` contra el metaschema canónico de **JSON Schema Draft 2020-12** utilizando la librería oficial `jsonschema.Draft202012Validator.check_schema()`.
   - Resultado: **0 errores de sintaxis, esquema 100% válido**.
2. **Paridad Total de Eventos (Markdown vs JSON):**
   - Verificación automatizada mediante script Python:
     - Cantidad de eventos en catálogo Markdown: **32**.
     - Cantidad de definiciones de eventos en `$defs` del JSON: **32**.
     - Cantidad de ramas en `oneOf` del JSON: **32**.
     - Paridad comprobada al **100%** (cero eventos huérfanos o discrepantes).
3. **Validación de Casos de Prueba:**
   - **Caso Usuario:** Evento interactivo `inbound_order_created` con UUIDs y sesión activa validado exitosamente contra el contrato.
   - **Caso Sistema:** Evento desatendido `stock_threshold_triggered` con `sessionId: null` y `userId: null` validado exitosamente demostrando compatibilidad con procesos background.
4. **Higiene de Datos y Cero PII:**
   - Inspección exhaustiva de ejemplos y esquemas: cero contraseñas, cero tokens JWT, cero emails en texto plano y cero datos sensibles expuestos.
5. **Integridad Git:**
   - Ejecución de `git status` y `git diff --check` verificando árbol de trabajo limpio y sin conflictos de espacios o archivos ajenos.

---

_Brasaland Digital — Monorepo de Operaciones Multi-Sede · Plan Canónico de Telemetría v1.0.0_
