# Checklist de Tareas — Hito de Infraestructura: Dockerización del Entorno de Desarrollo

## Fase 1: Alineación de Configuración y Rewrites
- [x] **Tarea 1.1: Actualizar `uis/backoffice/next.config.ts` con rewrite dinámico `INTERNAL_API_URL`**
  - **Archivo**: `uis/backoffice/next.config.ts`
  - **Acción**: Configurar el destino del rewrite `/api/:path*` leyendo `process.env.INTERNAL_API_URL` con fallback de desarrollo a `http://127.0.0.1:8000`. Limpiar slashes finales para evitar dobles barras.
  - **Criterio de Aceptación**: Soporta tanto llamadas internas en Docker (`http://backend:8000`) como ejecución local (`http://127.0.0.1:8000`).
- [x] **Tarea 1.2: Pruebas Automatizadas de URLs y Rewrites en Backoffice**
  - **Archivo**: `uis/backoffice/src/test/next-config-rewrites.test.ts`
  - **Acción**: Crear suite Vitest que verifique la configuración de rewrites con `INTERNAL_API_URL` configurado, sin configurar y con trailing slashes.
  - **Criterio de Aceptación**: Pruebas pasan al 100% en Vitest sin alterar el comportamiento existente de `inventory-api.test.ts`.
- [x] **Tarea 1.3: Actualizar `.env.example` y Validar `.gitignore`**
  - **Archivo**: `.env.example`, `.gitignore`
  - **Acción**: Conservar intactas todas las variables existentes (PostgreSQL, MongoDB, pgAdmin, backend) y añadir las variables requeridas por Docker (`DATABASE_URL`, `SUPPLIERS_DB_PATH`, `INTERNAL_API_URL`). Confirmar que `.env` y variantes locales siguen ignorados.
  - **Criterio de Aceptación**: Sin secretos ni contraseñas reales en `.env.example`. `.gitignore` intacto e ignorando `.env`.

> 🛑 **Checkpoint 1**: Validar suites existentes de backoffice y website (`npm run test:uis`, `typecheck`, `lint`, `build`). [COMPLETADO - 46 tests verdes, build 10/10]

---

## Fase 2: Contenerización de UIs (`uis`)
- [x] **Tarea 2.1: Crear `.dockerignore` para `uis`**
  - **Archivo**: `uis/.dockerignore`
  - **Acción**: Excluir `node_modules`, `.next`, `.env`, `.env.*`, `*.log`, `coverage`, `out`, `.DS_Store`.
  - **Criterio de Aceptación**: No incluye secretos ni artefactos compilados en el contexto de build.
- [x] **Tarea 2.2: Crear Script de Arranque y Supervisión de UIs `uis/start.sh`**
  - **Archivo**: `uis/start.sh`
  - **Acción**: Lanzar `website` en `0.0.0.0:3000` y `backoffice` en `0.0.0.0:3001`. Implementar trap para `SIGTERM`/`SIGINT`, monitoreo concurrente en bucle, salida con error si alguno falla y limpieza de procesos hijos. Otorgar permisos de ejecución (`chmod +x`).
  - **Criterio de Aceptación**: No usa `localhost`, maneja señales correctamente, evita procesos huérfanos.
- [x] **Tarea 2.3: Crear `uis/Dockerfile`**
  - **Archivo**: `uis/Dockerfile`
  - **Acción**: Basado en `node:22-alpine`. Contexto `./uis`. Copiar manifiestos `package*.json` de `website` y `backoffice`, instalar con `npm ci` si existe `package-lock.json` o fallback a `npm install --legacy-peer-deps`, exponer puertos 3000 y 3001, configurar usuario no-root `node`, ejecutar `uis/start.sh`.
  - **Criterio de Aceptación**: `docker build -f uis/Dockerfile uis` compila exitosamente sin errores.

> 🛑 **Checkpoint 2**: Construcción limpia de la imagen `uis` y verificación de que no depende de `node_modules` del host. [COMPLETADO - Imagen compilada]

---

## Fase 3: Contenerización del Backend (`services`)
- [x] **Tarea 3.1: Crear `.dockerignore` para `services`**
  - **Archivo**: `services/.dockerignore`
  - **Acción**: Excluir `__pycache__`, `*.pyc`, `.pytest_cache`, `.coverage`, `htmlcov`, `.env`, `.env.*`, `.venv`, `tests`, `*.egg-info`, `*.log`, `.DS_Store`.
  - **Criterio de Aceptación**: Preserva `api/pyproject.toml`, `api/uv.lock` y el código necesario de `services/api`.
- [x] **Tarea 3.2: Crear `services/Dockerfile`**
  - **Archivo**: `services/Dockerfile`
  - **Acción**: Basado en `python:3.12-slim`. Establecer explícitamente `WORKDIR /app/api`. Instalar `uv` oficial. Virtualenv en `/opt/venv` para evitar sobrescrituras por bind mounts. Instalar dependencias con `uv sync --active --frozen --no-dev`. Exponer puerto 8000. Configurar usuario no-root `appuser`. Comando de arranque Uvicorn con `--reload`.
  - **Criterio de Aceptación**: `docker build -f services/Dockerfile services` compila exitosamente sin errores.

> 🛑 **Checkpoint 3**: Construcción limpia de la imagen `services` y verificación de que el virtualenv reside fuera de `/app`. [COMPLETADO - Imagen compilada]

---

## Fase 4: Orquestación con Docker Compose Raíz
- [x] **Tarea 4.1: Crear `docker-compose.yml` en la Raíz**
  - **Archivo**: `docker-compose.yml`
  - **Acción**:
    - Declarar exactamente los servicios `interfaces` y `backend`.
    - Red dedicada `brasaland-dev`.
    - Servicio `interfaces`: build `./uis`, bind mount `./uis:/app`, volúmenes anónimos para `node_modules` y `.next`, puertos `3000:3000` y `3001:3001`, `INTERNAL_API_URL=http://backend:8000`, `depends_on` de `backend` con `condition: service_healthy`.
    - Servicio `backend`: build `./services`, bind mount `./services:/app`, puerto `8000:8000`, healthcheck contra `GET /health`, variables obligatorias `${DATABASE_URL:?...}` y `${SECRET_KEY:?...}`, `SUPPLIERS_DB_PATH=/app/api/data/suppliers.json`.
  - **Criterio de Aceptación**: Validación estática con `docker compose config` sin errores.

> 🛑 **Checkpoint 4**: `docker compose config` pasa exitosamente. Fallo controlado y legible cuando falten variables críticas. [COMPLETADO]

---

## Fase 5: Validación de Integración y Hot Reload
- [x] **Tarea 5.1: Validación de Servicios y Healthchecks**
  - **Acción**: Levantar el entorno con credenciales de prueba/PostgreSQL accesible si está disponible. Verificar `docker compose ps`, `GET /health` en 8000, Website en 3000 y Backoffice en 3001. Si no hay BD accesible desde Docker, detenerse y reportarlo conforme a la corrección 5.
  - **Criterio de Aceptación**: Ambos contenedores en estado `healthy` / `Up`.
- [x] **Tarea 5.2: Validación de Comunicación Interna Interfaces $\to$ Backend**
  - **Acción**: Ejecutar petición desde el contenedor de `interfaces` hacia `http://backend:8000/health`. Probar proxy rewrite `/api/health` desde el frontend.
  - **Criterio de Aceptación**: Resuelve el nombre de servicio `backend` sin recurrir a `localhost`.
- [x] **Tarea 5.3: Validación Controlada de Hot Reload en los Tres Procesos**
  - **Acción**:
    1. Realizar cambio temporal controlado (comentario inocuo) en `uis/website/src/app/page.tsx` y observar recompilación en logs.
    2. Realizar cambio temporal controlado en `uis/backoffice/src/app/page.tsx` y observar recompilación en logs.
    3. Realizar cambio temporal controlado en `services/api/app/main.py` y observar reinicio de Uvicorn en logs.
    4. Revertir de inmediato la edición exacta y verificar con `git status` y `git diff` que el árbol queda idéntico al estado original.
  - **Criterio de Aceptación**: Hot reload confirmado en logs sin bucles de reinicio y árbol de trabajo restaurado.

> 🛑 **Checkpoint 5**: Trazabilidad completa de hot reload y comunicación interna. [COMPLETADO]

---

## Fase 6: Documentación, Higiene y Entrega
- [x] **Tarea 6.1: Actualizar `README.md` y `README.es.md`**
  - **Archivos**: `README.md`, `README.es.md`
  - **Acción**: Documentar el comando `docker compose up --build`, variables de `.env`, puertos expuestos, parada con `docker compose down`.
  - **Criterio de Aceptación**: Instrucciones claras, reproducibles y sin secretos.
- [x] **Tarea 6.2: Actualizar `memory-bank/progress.md`**
  - **Archivo**: `memory-bank/progress.md`
  - **Acción**: Registrar el hito de infraestructura Docker, componentes creados y estado del monorepo.
  - **Criterio de Aceptación**: Refleja el estado actual de la plataforma.
- [x] **Tarea 6.3: Crear `tasks/docker-development-walkthrough.md`**
  - **Archivo**: `tasks/docker-development-walkthrough.md`
  - **Acción**: Compilar evidencias completas: arquitectura, comandos, salidas de build, `docker compose ps`, resolución interna, hot reload, notas sobre base de datos.
  - **Criterio de Aceptación**: Documento detallado y verificable.
- [x] **Tarea 6.4: Auditoría Final de Seguridad y Estado Git**
  - **Acción**: Ejecutar `git status`, `git diff`, verificar que `.env` no está rastreado, que no se agregaron artefactos no deseados (`.next`, `node_modules`, caches).
  - **Criterio de Aceptación**: Repositorio limpio, sin commits ni pushes sin autorización.
