# 🎯 Historial de Proyectos — Brasaland

> Notas técnicas de cada hito completado, para mantener contexto y tracción entre entregas.

---

## **`🗄️ Backend de Inventario — ORM + Doble Base de Datos`**

### 🧠 ¿Qué hice?

Construí el backend de inventario de Brasaland en `services/backend` (rama
`feature/db-inventario`): FastAPI + SQLAlchemy sobre PostgreSQL para el inventario
transaccional, y MongoDB para documentos anidados (recetas y auditoría) — el
requisito de "doble base de datos" del hito.

### Lo que incluye

1. **Modelos ORM** (Local, Proveedor, Ingrediente, InventarioLocal, Movimiento,
   Usuario) con migraciones **Alembic** (`alembic upgrade head`).
2. **28 endpoints REST** bajo `/api/v1/` con patrón router → service → repository,
   paginado, búsqueda, JWT Bearer en escrituras y errores de negocio → 400.
3. **Reglas de negocio**: movimientos atómicos (entrada/salida/ajuste con rollback),
   alertas de reposición con déficit, borrado lógico de ingredientes con stock,
   moneda derivada del país (CO→COP, US→USD).
4. **MongoDB**: recetas con ingredientes y pasos anidados + auditoría de operaciones.
5. **Seed idempotente** (re-ejecutar no duplica: claves naturales).
6. **23 tests pytest verdes** con PostgreSQL/MongoDB efímeros.
7. **README con guion del video de 5 min** (7 puntos del hito).

---

## **`</> Propuesta de Arquitectura de Backend`**

### 🧠 ¿Qué hice?

Redacté el documento **`docs/ARCHITECTURE_PROPOSAL.md`** — la propuesta de arquitectura del backend de Brasaland que el CTO (Nicolás) pidió antes de empezar a programar.

### La decisión central

Elegí un **Monolito Modular con capas por dominio** — ¿qué significa eso?

- **Monolito**: todo el backend es una sola aplicación que se despliega junta. No microservicios.
- **Modular**: el código está organizado en **10 dominios de negocio** (locales, menú, ventas, inventario, compras, clientes, lealtad, RRHH, capacitación, analytics).
- **Capas**: cada dominio se divide en router → service → repository (la estructura clásica de FastAPI).

### ¿Por qué?

| Para Brasaland | Para el equipo |
|---|---|
| 14 locales, 2 países, mucha complejidad real | Equipo pequeño, evitar sobreingeniería |
| Datos en tiempo real (ventas, stock) | FastAPI es async nativo |
| Múltiples frontends (app, web, backoffice) | Una API unificada sirve a todos |

### Lo que incluye el documento

1. **Patrón arquitectónico** y por qué descarté microservicios, serverless, MVC y hexagonal.
2. **Estructura de carpetas** completa (`services/backend/`) siguiendo las convenciones oficiales de FastAPI.
3. **Rutas y endpoints** organizados por dominio con tabla detallada.
4. **Separación frontend/backend** — monorepo compartido, CORS, JWT, variables de entorno.
5. **Decisiones técnicas** — FastAPI, PostgreSQL, SQLAlchemy async, Redis, Docker.
6. **5 riesgos** con mitigaciones concretas (acoplamiento, common/ desordenado, confusión Pydantic vs SQLAlchemy, etc.).

---

*Documento interno — Brasaland Digital*