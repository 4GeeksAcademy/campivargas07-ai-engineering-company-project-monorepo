# Brasaland Backend — Gestión de Inventario (hito: ORM + doble BD)

API REST con **FastAPI + SQLAlchemy (PostgreSQL)** para el inventario de la cadena de
restaurantes Brasaland, y **MongoDB** para documentos anidados (recetas y auditoría).
Incluye migraciones con **Alembic**, seed idempotente, JWT y suite de tests.

## Stack

| Capa | Tecnología |
|---|---|
| Framework | FastAPI 0.141 (síncrono) |
| ORM | SQLAlchemy 2.0 + psycopg2 |
| BD relacional | PostgreSQL 16 (Docker) |
| BD documental | MongoDB (Docker, pymongo) |
| Migraciones | Alembic |
| Auth | JWT Bearer (python-jose + passlib/bcrypt) |
| Tests | pytest + TestClient, BDs efímeras |
| Gestor de paquetes | uv |

## Arquitectura

Monolito modular con separación en tres capas por dominio:

```
app/
├── main.py              # app FastAPI, routers, lifespan (conexión Mongo)
├── config.py            # Settings (pydantic-settings), .env de la raíz
├── database.py          # engine + SessionLocal (PostgreSQL)
├── mongo.py             # conexión MongoDB (recetas, auditoria)
├── common/base.py       # Base declarativa SQLAlchemy
├── core/                # seguridad JWT, dependencias (get_db, get_current_user)
└── domains/
    ├── auth/            # login → JWT
    ├── locations/       # locales (regla moneda-país)
    ├── ingredients/     # ingredientes + borrado lógico
    ├── procurement/     # proveedores + relación con locales
    ├── inventory/       # inventario por local, movimientos, kardex, alertas
    └── recipes/         # recetas en Mongo (documentos anidados) + auditoría
```

Cada dominio sigue `router → service → repository` (o service directo cuando la
consulta es simple). Los errores de negocio suben como excepciones de dominio y el
router las traduce a HTTP 400; la validación de Pydantic responde 422.

## Cómo correr

```bash
# 1. Bases de datos (desde la raíz del monorepo)
docker compose up -d          # postgres:5432, mongo:27017, pgadmin

# 2. Backend
cd services/backend
uv sync                                        # instalar dependencias
uv run alembic upgrade head                    # crear esquema (tabla alembic_version)
uv run python scripts/seed.py                  # datos demo (idempotente)
uv run uvicorn app.main:app --reload --port 8001
```

Swagger UI: **http://localhost:8001/docs** · ReDoc: `/redoc` · Health: `/health`.

> El puerto es 8001 porque `services/api` (hito anterior) ocupa el 8000.

### Credenciales del seed

| Usuario | Contraseña | Rol |
|---|---|---|
| admin@brasaland.com | admin123 | admin |
| operador@brasaland.com | operador123 | operador |
| consulta@brasaland.com | consulta123 | consulta |

Login: `POST /api/v1/auth/token` con `username` y `password` (form-data, OAuth2).
Todas las escrituras requieren header `Authorization: Bearer <token>`.

## Endpoints (28 operaciones, 18 rutas)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Estado del servicio y BD |
| POST | `/api/v1/auth/token` | Login → JWT |
| GET/POST | `/api/v1/locales` | Listar / crear local |
| GET/PUT/DELETE | `/api/v1/locales/{id}` | Detalle / actualizar / borrar |
| GET/POST | `/api/v1/ingredientes` | Listar (paginado+búsqueda) / crear |
| GET/PUT/DELETE | `/api/v1/ingredientes/{id}` | Detalle / actualizar / borrar (lógico si tiene inventario) |
| GET/POST | `/api/v1/proveedores` | Listar / crear proveedor |
| GET/PUT/DELETE | `/api/v1/proveedores/{id}` | Detalle / actualizar / borrar |
| GET/POST/DELETE | `/api/v1/proveedores/{id}/locales[/{local_id}]` | Locales atendidos por proveedor |
| GET | `/api/v1/inventario` | Stock por local (paginado) |
| GET | `/api/v1/inventario/alertas` | Ítems bajo el mínimo, con déficit |
| POST | `/api/v1/inventario/movimientos` | Entrada / salida / ajuste (transacción atómica) |
| GET | `/api/v1/inventario/{id}/movimientos` | Kardex del ítem |
| GET/POST | `/api/v1/recetas` | Recetas en MongoDB (ingredientes y pasos anidados) |
| GET | `/api/v1/recetas/buscar?plato=` | Búsqueda case-insensitive |
| GET | `/api/v1/recetas/{id}` | Detalle por ObjectId |
| GET | `/api/v1/auditoria` | Últimos eventos de auditoría (MongoDB) |

## Reglas de negocio

- **Moneda por país**: `CO → COP`, `US → USD`; otro país → 422.
- **Movimientos atómicos**: entrada acumula, salida valida stock (400 si excede),
  ajuste fija el conteo físico; todo en una transacción con rollback.
- **Borrado de ingredientes**: si tiene filas de inventario → borrado lógico
  (`activo=false`); si no → físico.
- **Alertas**: `cantidad_actual <= cantidad_minima` por local, con `deficit`.
- **Idempotencia del seed**: claves naturales (código de ingrediente, `motivo`
  determinista en movimientos); re-ejecutarlo no duplica datos.

## Tests

```bash
uv run pytest -v        # 23 tests
```

`tests/conftest.py` crea **PostgreSQL y MongoDB efímeros** (`brasaland_test_db`,
`brasaland_test`), aplica el esquema con `Base.metadata.create_all`, overridea la
dependencia `get_db` y autentica con un usuario admin de prueba. Sin tocar la BD de
desarrollo.

## Migraciones

```bash
uv run alembic revision --autogenerate -m "mensaje"   # generar
uv run alembic upgrade head                           # aplicar
uv run alembic downgrade -1                           # revertir
```

El estado vigente vive en la tabla `alembic_version` (visible en el video del hito).

## Guion del video (5 min, 7 puntos)

1. **(0:00) Backend corriendo** — terminal con `uvicorn app.main:app --port 8001` y
   log "MongoDB conectado"; abrir `/health` en el navegador.
2. **(0:30) Swagger** — recorrer `/docs`: grupos auth, locales, ingredientes,
   proveedores, inventario, recetas-mongo; ejecutar Authorize con
   `admin@brasaland.com / admin123`.
3. **(1:15) CRUD en PostgreSQL** — desde Swagger: crear local (201), listar
   ingredientes paginado (200), actualizar costo (200), borrar ingrediente con
   inventario (200, borrado lógico) y sin inventario (físico); mencionar códigos
   201/200/400/401/404/422.
4. **(2:15) Operación anidada en Mongo** — `POST /api/v1/recetas` con ingredientes y
   pasos anidados, `GET /recetas/buscar`, `GET /auditoria`; explicar el documento y
   la referencia `ingrediente_id` hacia PostgreSQL.
5. **(3:00) Migraciones** — correr `uv run alembic upgrade head` en vivo; mostrar la
   tabla `alembic_version` y el historial en `\dt` (psql) o pgAdmin.
6. **(3:45) Seed idempotente** — correr `uv run python scripts/seed.py` dos veces;
   segunda corrida sin duplicados; mostrar datos en Swagger (locales, alertas).
7. **(4:15) Arquitectura** — breve explicación del diagrama router → service →
   repository, doble BD (relacional vs documentos) y cierre con `uv run pytest` en
   verde (23 tests).