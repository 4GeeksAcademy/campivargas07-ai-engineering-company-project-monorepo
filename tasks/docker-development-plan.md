# Plan de Implementación — Hito de Infraestructura: Dockerización del Entorno de Desarrollo

## 1. Estado Inicial Confirmado

### 1.1 Verificación de Rama y Checkout
- **Rama activa**: `feature/backoffice-inventario` (rastreando `origin/feature/backoffice-inventario`).
- **Commit HEAD**: `ad0f0f4` (*"Pruebas visuales completadas"*).
- **Relación con PR #12**: Se ha confirmado mediante `gh pr view 12` y `git status` que el checkout local contiene íntegramente los cambios de la PR #12 (`feat(inventory-ui): Backoffice de Gestión de Inventario (Hito 5)`).
- **Estado del árbol de trabajo**: Limpio (`nothing to commit, working tree clean`).
- **Ubicación real de TinyDB (`suppliers.json`)**:
  - `services/api/data/suppliers.json`: Archivo rastreado en Git desde el commit `5bbdbbf` (Hito 5 / Doble BD).
  - `services/data/suppliers.json`: Archivo rastreado desde `77d66db` en `services/data/`.
  - En `services/api/.env`, `SUPPLIERS_DB_PATH=data/suppliers.json` (relativo a `services/api`).
  - **Decisión**: No mover ni duplicar la base TinyDB. Mantener `/app/api/data/suppliers.json` en Docker manteniendo la correspondencia con `./services/api/data/suppliers.json`.
- **Estado de credenciales / base de datos (`DATABASE_URL`)**:
  - En `services/api/.env`, `DATABASE_URL` está configurada como `postgresql://postgres:postgres@localhost:5432/brasaland_db`.
  - En el archivo `.env` de la raíz del monorepo, `DATABASE_URL` no está definida.
  - **Bloqueo crítico reportado**: Dentro de una red Docker, el host `localhost` apunta a la interfaz loopback del propio contenedor (`backend`), donde no corre PostgreSQL. Por lo tanto, una URL con host `localhost` no funcionará dentro del contenedor.
  - Conforme a las reglas del hito y confirmación del usuario:
    1. No se añadirá silenciosamente PostgreSQL, MongoDB o pgAdmin al Compose raíz.
    2. No se utilizará `host.docker.internal` como solución final.
    3. La conexión esperada es PostgreSQL externo / Supabase.
    4. El Compose raíz exigirá `DATABASE_URL` y `SECRET_KEY` desde el entorno sin fallbacks inseguros ni credenciales hardcodeadas.

### 1.2 Validación de Línea Base Previa
- **Website (`uis/website`)**:
  - `typecheck`: 0 errores.
  - `lint`: 0 errores.
  - `build`: Exitoso (Next.js 16.2.10 Turbopack, 5 rutas estáticas).
- **Backoffice (`uis/backoffice`)**:
  - `test`: 39 pruebas pasando (8 suites).
  - `typecheck`: 0 errores.
  - `lint`: 0 errores.
  - `build`: Exitoso (Next.js 16.2.10 Turbopack, 10 rutas estáticas).
- **Pruebas globales UI**:
  - `npm run test:uis`: 43 pruebas pasando (39 backoffice + 4 website).
- **Backend (`services/api`)**:
  - `TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/brasaland_api_test" uv run pytest`: 65 pruebas pasando al 100% (0 errores, 0 fallos).

---

## 2. Archivos Afectados

### Archivos Nuevos
1. `docker-compose.yml`: Orquestación raíz con los servicios `interfaces` y `backend`, red dedicada `brasaland-dev`.
2. `uis/Dockerfile`: Construcción de imagen Node.js Alpine única para `website` (puerto 3000) y `backoffice` (puerto 3001).
3. `uis/.dockerignore`: Exclusión de `node_modules`, `.next`, secretos `.env*`, caches y logs.
4. `uis/start.sh`: Script ejecutable de arranque concurrente y supervisión de procesos para ambos frontends con manejo de señales POSIX.
5. `services/Dockerfile`: Construcción de imagen Python 3.12-slim con `uv`, `WORKDIR /app/api`, virtualenv aislado en `/opt/venv` y Uvicorn con `--reload`.
6. `services/.dockerignore`: Exclusión de caches Python, `.venv`, `.pytest_cache`, `.env*` y tests de la imagen.
7. `uis/backoffice/src/test/next-config-rewrites.test.ts`: Pruebas automatizadas para verificar el rewrite dinámico con `INTERNAL_API_URL`.
8. `tasks/docker-development-plan.md`: Este documento.
9. `tasks/docker-development-todo.md`: Checklist de seguimiento y criterios de aceptación.
10. `tasks/docker-development-walkthrough.md`: Evidencias de construcción, validación, hot reload y trazabilidad.

### Archivos Modificados
1. `uis/backoffice/next.config.ts`: Modificación del rewrite `/api/:path*` para resolver dinámicamente según `INTERNAL_API_URL` con fallback a `http://127.0.0.1:8000`.
2. `.env.example`: Conservar todas las variables existentes (PostgreSQL, MongoDB, pgAdmin, backend heredado) y añadir exclusivamente las nuevas variables necesarias para Docker (`DATABASE_URL`, `SUPPLIERS_DB_PATH`, `INTERNAL_API_URL`).
3. `README.md` y `README.es.md`: Documentación de uso de Docker Compose para desarrolladores.
4. `memory-bank/progress.md`: Registro del hito de infraestructura Docker.

### Archivos Protegidos (Sin Modificación)
- `infra/docker-compose.yml` (se conserva intacto para servicios de datos).
- `scripts/start-all.sh` (se conserva para desarrollo local fuera de Docker).
- `services/backend/` (código heredado preservado).
- `memory-bank/projectbrief.md` y `memory-bank/techContext.md`.
- `CONTEXT.md` y `company-choice.md`.

---

## 3. Grafo de Dependencias y Arquitectura

```mermaid
flowchart TD
    subgraph Host["Host Developer Machine"]
        HostBrowser["Navegador Web del Desarrollador"]
        HostFS["Sistema de Archivos del Host"]
    end

    subgraph DockerNet["Red Docker: brasaland-dev"]
        subgraph InterfacesContainer["Contenedor: interfaces (uis/Dockerfile)"]
            NextWebsite["Next.js Website (:3000)"]
            NextBackoffice["Next.js Backoffice (:3001)"]
            NextRewrite["Rewrite Proxy (/api/*)"]
            NextBackoffice --> NextRewrite
        end

        subgraph BackendContainer["Contenedor: backend (services/Dockerfile)"]
            FastAPIApp["FastAPI Uvicorn (app.main:app :8000)"]
            HealthEndpoint["GET /health"]
        end
    end

    subgraph ExternalServices["Servicios Externos / Persistencia"]
        ExternalDB[("PostgreSQL / Supabase")]
        TinyDBFile[("TinyDB: services/api/data/suppliers.json (Bind Mount)")]
    end

    %% Host bindings
    HostFS -.->|"Bind mount: ./uis -> /app"| InterfacesContainer
    HostFS -.->|"Bind mount: ./services -> /app"| BackendContainer
    HostFS -.->|"Persistencia archivo"| TinyDBFile

    %% Port Publishing
    HostBrowser -->|"http://localhost:3000"| NextWebsite
    HostBrowser -->|"http://localhost:3001"| NextBackoffice
    HostBrowser -->|"http://localhost:8000 (docs/direct)"| FastAPIApp

    %% Internal Network Resolution
    NextRewrite -->|"http://backend:8000/* (INTERNAL_API_URL)"| FastAPIApp
    InterfacesContainer -->|"depends_on: condition: service_healthy"| BackendContainer

    %% Backend Dependencies
    FastAPIApp -->|"DATABASE_URL (TCP)"| ExternalDB
    FastAPIApp -->|"SUPPLIERS_DB_PATH"| TinyDBFile
```

---

## 4. Decisiones de Imágenes y Versiones

| Componente | Imagen Base Oficial | Justificación |
|---|---|---|
| `interfaces` | `node:22-alpine` | Versión LTS compatible con Next.js 16.2.10 y React 19.2.4. Alpine reduce la superficie de ataque y tamaño (~150MB). Incluye usuario no-root `node` (UID 1000). |
| `backend` | `python:3.12-slim` | Versión compatible con `pyproject.toml` (`requires-python = ">=3.11"`). Distribución Debian slim con librerías glibc necesarias para `psycopg2-binary` y extensiones C de Pydantic/Bcrypt. |
| Herramienta Python | `ghcr.io/astral-sh/uv:0.12.3` | Se extraen binarios de `uv` y `uvx` mediante multi-stage copy (`COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/`). Garantiza paridad con el gestor local. |

---

## 5. Estrategia de Instalación de Dependencias

### 5.1 Interfaces (`uis`)
- **Contexto de construcción**: `./uis`.
- **Estrategia**:
  1. Copiar manifiestos `website/package*.json` y `backoffice/package*.json` a `/app/website/` y `/app/backoffice/`.
  2. Ejecutar condicionalmente: si existe `package-lock.json`, usar `npm ci --no-audit --no-fund`; si no existe, usar `npm install --no-audit --no-fund`.
  3. Aprovechar la caché de capas de Docker para no reinstalar salvo cambios en los manifiestos.
  4. Copiar el código fuente y el script de arranque.
  5. Asignar propiedad de archivos al usuario no-root `node:node` (UID 1000).
  6. Configurar volúmenes anónimos en Docker Compose para evitar que el bind mount del host sobrescriba o contamine `/app/website/node_modules` y `/app/backoffice/node_modules`.

### 5.2 Backend (`services`)
- **Contexto de construcción**: `./services`.
- **Estrategia**:
  1. Establecer explícitamente `WORKDIR /app/api` desde el inicio de la imagen.
  2. Copiar manifiestos `api/pyproject.toml` y `api/uv.lock` a `/app/api/`.
  3. Crear entorno virtual dedicado en `/opt/venv` (fuera de `/app` para no ser enmascarado por el bind mount del código fuente).
  4. Instalar dependencias con `uv sync --active --frozen --no-dev` ejecutado dentro de `/app/api`.
  5. Copiar código fuente de `api/` a `/app/api` y `data/` a `/app/data`.
  6. Crear usuario no-root `appuser` (UID 1000, compatible con Codespaces) y asignar permisos.

---

## 6. Bind Mounts y Volúmenes

### 6.1 Aislamiento Estricto
Para satisfacer la restricción de que `node_modules`, `.next` y `.venv` no contaminen el host ni sean sobreescritos:
- **`interfaces`**:
  - Bind mount: `./uis:/app`
  - Volúmenes anónimos:
    - `/app/website/node_modules`
    - `/app/backoffice/node_modules`
    - `/app/website/.next`
    - `/app/backoffice/.next`
- **`backend`**:
  - Bind mount: `./services:/app`
  - El entorno virtual reside en `/opt/venv`, completamente fuera del árbol `/app`, haciendo imposible colisiones con `.venv` del host.
  - Persistencia de TinyDB: mapeo directo a través del bind mount respetando la ubicación real existente `./services/api/data/suppliers.json` (mapeada a `/app/api/data/suppliers.json` en el contenedor).

---

## 7. Red y Resolución de Servicios

- **Nombre de red**: `brasaland-dev` (driver bridge explícito).
- **Comunicación Contenedor $\to$ Contenedor**:
  - `interfaces` se comunica con `backend` a través de `http://backend:8000`.
  - Prohibido el uso de `localhost` o `127.0.0.1` entre contenedores.
- **Comunicación Navegador $\to$ Backend**:
  - El navegador del usuario no resuelve el hostname `backend`.
  - Las peticiones del cliente frontend se dirigen a `/api/*`.
  - El servidor Next.js en `uis/backoffice` reescribe `/api/*` hacia `${INTERNAL_API_URL}/*` (`http://backend:8000/*` en Docker, `http://127.0.0.1:8000/*` en desarrollo local).
  - No se configura `NEXT_PUBLIC_INVENTORY_API_URL=http://backend:8000`. Si `NEXT_PUBLIC_INVENTORY_API_URL` está definido fuera de Docker, se respeta su precedencia.

---

## 8. Variables de Entorno y Manejo Seguro

### 8.1 Compose Raíz (`docker-compose.yml`)
- Variables requeridas sin fallback silencioso:
  - `DATABASE_URL=${DATABASE_URL:?DATABASE_URL is required}`
  - `SECRET_KEY=${SECRET_KEY:?SECRET_KEY is required}`
- Variables con valores por defecto seguros:
  - `ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES:-60}`
  - `SUPPLIERS_DB_PATH=${SUPPLIERS_DB_PATH:-/app/api/data/suppliers.json}`
  - `INTERNAL_API_URL=${INTERNAL_API_URL:-http://backend:8000}`
  - `WATCHPACK_POLLING=${WATCHPACK_POLLING:-true}` (para fiabilidad de hot reload en Linux/Docker)

### 8.2 Plantilla `.env.example`
Se conservan todas las variables existentes intactas y se añaden las requeridas por Docker:
```dotenv
# ============================================================
#  Brasaland — Variables de entorno (Hito: Doble Base de Datos)
#  Copia este archivo a .env  →  cp .env.example .env
#  NUNCA subas el archivo .env real al repositorio.
# ============================================================

# --- PostgreSQL (docker-compose: infra/docker-compose.yml) ---
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=brasaland_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# --- MongoDB ---
MONGO_USER=brasaland
MONGO_PASSWORD=brasaland
MONGO_DB=brasaland
MONGO_HOST=localhost
MONGO_PORT=27017

# --- pgAdmin (GUI opcional, http://localhost:5050) ---
PGADMIN_EMAIL=admin@brasaland.com
PGADMIN_PASSWORD=admin

# --- Backend (services/backend) ---
BACKEND_PORT=8001
SECRET_KEY=cambia-esta-clave-en-produccion
ACCESS_TOKEN_EXPIRE_MINUTES=30

# --- Entorno Docker (docker-compose.yml raíz) ---
# URL de conexión a PostgreSQL requerida por el backend en Docker (PostgreSQL accesible o Supabase)
# NOTA: Dentro del contenedor Docker no se debe usar "localhost".
DATABASE_URL=postgresql://postgres:postgres@host-remoto:5432/brasaland_db

# Ruta del archivo TinyDB dentro del contenedor backend
SUPPLIERS_DB_PATH=/app/api/data/suppliers.json

# URL de resolución interna entre interfaces y backend en Docker
INTERNAL_API_URL=http://backend:8000
```

---

## 9. Healthchecks y Control de Inicio

- **Backend Healthcheck**:
  ```yaml
  healthcheck:
    test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"]
    interval: 5s
    timeout: 3s
    retries: 5
    start_period: 10s
  ```
- **Interfaces Dependencia**:
  ```yaml
  depends_on:
    backend:
      condition: service_healthy
  ```

---

## 10. Hot Reload y Protocolo de Verificación Segura

- **Website / Backoffice**:
  - `next dev -H 0.0.0.0 -p 3000` y `-p 3001`.
  - Detección de cambios mediante bind mount de `./uis` a `/app`.
  - Inyección de `WATCHPACK_POLLING=true` para garantizar propagación instantánea de eventos de inotify en Docker.
- **Backend (FastAPI)**:
  - `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
  - Supervisión activa del directorio `/app/api`.
  - Recarga automática del proceso ante cambios en archivos `.py`.
- **Protocolo de Verificación Segura**:
  - Se realiza un cambio temporal controlado (añadir un comentario inocuo en una línea nueva).
  - Se confirma en logs la detección del cambio y la recarga.
  - Se revierte inmediatamente la edición exacta.
  - Se verifica con `git status` y `git diff` que el árbol de trabajo queda exactamente limpio como estaba originalmente.

---

## 11. Validaciones Automatizadas

1. **Validación estática**:
   - `docker compose config` con `.env.example` / archivo temporal de prueba.
   - `docker build -f uis/Dockerfile uis`.
   - `docker build -f services/Dockerfile services`.
2. **Pruebas de regresión del monorepo**:
   - Website: `typecheck`, `lint`, `build`.
   - Backoffice: `test`, `typecheck`, `lint`, `build`.
   - Global: `npm run test:uis`.
   - Backend: `TEST_DATABASE_URL=... uv run pytest`.
3. **Pruebas de URLs y rewrites**:
   - `uis/backoffice/src/test/next-config-rewrites.test.ts`.

---

## 12. Procedimiento de Prueba Manual

1. Con `.env` conteniendo variables válidas y PostgreSQL accesible:
   - `docker compose up --build -d`
   - `docker compose ps` (ambos servicios en estado `Up` / `healthy`)
   - `curl -f http://localhost:8000/health` $\to$ `{"status":"ok"}`
   - `curl -f http://localhost:8000/docs` $\to$ HTTP 200
   - `curl -f http://localhost:3000` $\to$ HTTP 200 (Website)
   - `curl -f http://localhost:3001/login` $\to$ HTTP 200 (Backoffice)
2. Desde el contenedor de interfaces:
   - `docker compose exec interfaces wget -qO- http://backend:8000/health` $\to$ HTTP 200 `{"status":"ok"}`
3. Prueba controlada de Hot Reload (con verificación de limpieza Git).
4. Parada limpia: `docker compose down` (sin `-v`).
