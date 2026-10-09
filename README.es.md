# Proyecto de Compañía - Ingeniería de IA — Plantilla para estudiantes

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Plantilla base para proyectos transversales del Programa de Carrera en Ingeniería de IA — 4Geeks Academy._

_Las instrucciones están [disponibles en inglés](./README.md)._

---

## Propósito

Este repositorio es la **plantilla de inicio** para los proyectos transversales. Trabajarás con escenarios de empresas reales (Brasaland, TrackFlow, Nexova) construyendo entregables que se corresponden con los hitos del curso (Web, Programación, Backend, Telemetría, RAG, Agentes, Workflows, Tiempo real).

- Crea una plantilla a partir de este repositorio.
- Reemplaza el `CONTEXT.md` placeholder por el contexto de tu empresa asignada.
- Usa `skills/` y los `README.md` por carpeta como guía de trabajo.

---

## Estado actual de la plantilla

Actualmente el repositorio ofrece una **estructura base de carpetas y documentación**, pero todavía no incluye aplicaciones ejecutables ni scripts globales en la raíz.

- `CONTEXT.md` es un placeholder y debe sustituirse por el contexto de la empresa asignada.
- No existe todavía un `AGENTS.md` en la raíz.
- Existe metadata del paquete compartido en `packages/shared/package.json` (`@repo/shared-types`), pero aún no hay runner de workspace en raíz.

---

## Estructura del repositorio

```text
ai-engineering-company-project-monorepo/
├── README.md
├── README.es.md
├── CONTEXT.md                # Placeholder a reemplazar con el contexto asignado
├── agents/                   # Patrones/plantillas de agentes y documentación de tools
├── data/                     # raw, process, pipelines, eval
├── docs/                     # Documentación de proyecto y arquitectura
├── infra/                    # Docker, Terraform, configuraciones de despliegue
├── internal/                 # CLIs, scripts de migración empaquetados, utilidades internas
├── mcps/                     # Servidores Model Context Protocol (MCP)
├── packages/
│   └── shared/               # Paquete compartido (@repo/shared-types)
├── scripts/                  # Convenciones/documentación de scripts
├── services/                 # APIs y workers en segundo plano
├── shared/                   # Recursos/convenciones compartidas a nivel repo
├── skills/                   # Skills reutilizables para agentes
├── uis/                      # Interfaces de usuario (React, Next.js, Streamlit, HTML)
└── workflows/                # Documentación de automatizaciones/orquestación
```

---

## Entorno de Desarrollo con Docker

Todo el stack de desarrollo se inicia con un único comando de Docker Compose desde la raíz del repositorio:

```bash
# 1. Preparar las variables de entorno
cp .env.example .env
# Configura en .env tu DATABASE_URL de PostgreSQL accesible y tu SECRET_KEY

# 2. Construir e iniciar los servicios
docker compose up --build
```

### Servicios y Puertos Publicados

| Servicio | Tecnología | Puerto Interno | Puerto Publicado | Descripción |
|---|---|---|---|---|
| `interfaces` | Next.js 16 (Node 22 Alpine) | 3000, 3001 | `http://localhost:3000`<br>`http://localhost:3001` | Contenedor único ejecutando Website (3000) y Backoffice (3001) |
| `backend` | FastAPI (Python 3.12 Slim, uv) | 8000 | `http://localhost:8000` | API de operaciones, inventario, autenticación e incidencias (`/health`, `/docs`) |

### Características Principales

- **Red Interna**: Los servicios se comunican a través de la red bridge `brasaland-dev` utilizando los nombres de host de servicio Docker (`http://backend:8000`).
- **Proxy Rewrites de Cliente**: El navegador interactúa con `/api/*` mediante reescrituras en el servidor Next.js orientadas a `INTERNAL_API_URL`.
- **Recarga en Caliente (Hot Reload)**: Los cambios en tiempo real en `uis/` y `services/` disparan recargas instantáneas vía bind mounts sin reconstruir contenedores.
- **Detención Segura de Servicios**:
  ```bash
  docker compose down
  ```
  *(Evita `docker compose down -v` para no eliminar accidentalmente los volúmenes de datos).*

---

## Hitos (referencia)

| Hito | Enfoque       | Entregables típicos                              |
| ---- | ------------- | ------------------------------------------------ |
| 0    | Prework       | Configuración del entorno, primeros prompts      |
| 1    | Web           | Sitio corporativo, formularios, SEO              |
| 2    | Programación  | Lógica de negocio, puntuación, cálculos          |
| 3    | UI con IA     | Interfaces generadas con IA                      |
| 4    | Next.js       | Portales, app de fidelización, UI de operaciones |
| 5    | Backend       | API central (ubicaciones, menús, ventas, etc.)   |
| 6    | Telemetría    | Pipeline de datos, dashboards                    |
| 7    | RAG y memoria | Base de conocimiento semántica, búsqueda         |
| 8    | Agentes       | Agentes de soporte, onboarding, formación        |
| 9    | Workflows     | Automatizaciones con n8n                         |
| 10   | Tiempo real   | Dashboards en vivo, alertas, streaming           |

---

## Enlaces

- [4Geeks Academy — Ingeniería de IA](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [Cómo empezar un proyecto de código](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contribuidores

Esta plantilla fue creada como parte del Programa de Carrera de Ingeniería de IA de 4Geeks Academy por [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) y [@alezanchezr](https://x.com/alesanchezr), junto a otros muchos colaboradores. Descubre más sobre nuestro [Curso de Ingeniería de IA](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia) y sobre [otros cursos](https://4geeksacademy.com/es/comparar-programas).

Puedes encontrar otras plantillas y recursos similares en la [página de GitHub de 4Geeks Academy](https://github.com/4geeksacademy).

_Esta plantilla la mantiene 4Geeks Academy para el track de Ingeniería de IA. Uso exclusivo del programa._
# DEV-55: corridas asíncronas de salud de inventario

`POST /reporting/inventory-health/runs` requiere un usuario `admin` o `manager`
y publica en Redis una tarea Celery con **solo el UUID de la corrida**. Devuelve
`202`, los campos anteriores y `task_id`, idéntico a `flow_run_id`. El worker
independiente recupera los datos de PostgreSQL y llama al pipeline Prefect
existente. El proceso nocturno, cron y `job_runs` mantienen sus contratos.

Configura `.env` con `DATABASE_URL` accesible desde los contenedores,
`SECRET_KEY`, `REDIS_URL=redis://redis:6379/0` y credenciales locales propias
`FLOWER_BASIC_AUTH=usuario:contraseña`. Las migraciones de reporting anteriores
deben estar aplicadas. La migración `services/api/migrations/004_create_async_tasks.sql`
crea `async_tasks` y `task_dead_letters`; la API también registra estas tablas
mediante `init_db()`. No configura ni modifica un cron.

```bash
# Redis y worker pueden vivir sin la API.
docker compose up -d --build redis backend worker
# Monitor opcional: exige FLOWER_BASIC_AUTH; solo escucha en localhost:5555.
docker compose --profile monitoring up -d --build flower
docker compose logs -f worker
# Detener sin borrar datos persistentes; el worker tiene parada gradual.
docker compose --profile monitoring stop backend worker flower redis
# Retirar contenedores conservando los volúmenes AOF y Flower.
docker compose --profile monitoring down
```

Redis usa imagen oficial, AOF (`appendfsync everysec`), volumen persistente y
`noeviction`; el puerto de desarrollo 6379 escucha solo en localhost. Flower
usa autenticación HTTP Basic, perfil `monitoring`, almacenamiento persistente y
puerto 5555 solo en localhost. En Codespaces, mantén el puerto reenviado privado.
El build de `services/Dockerfile` usa contexto raíz e incluye `data/pipelines/`;
los bind mounts de desarrollo de la API conservan ese import mediante `PYTHONPATH`.

Consulta `GET /tasks/{task_id}` con Bearer: devuelve
`{task_id, status, result}`, con estados `pending` (PENDING/RECEIVED/RETRY),
`started`, `success` o `failure` (también REVOKED). Un UUID desconocido retorna
`404`; un resultado terminal de más de 24 horas retorna `410`. El registro
PostgreSQL distingue IDs reales de la respuesta PENDING genérica de Celery y
conserva resultados ante pérdida de la clave Redis. Un fallo del broker al
publicar devuelve `503` y deja la corrida `FAILED`, nunca un `202` engañoso.
La consulta anterior `GET /reporting/inventory-health/runs/{flow_run_id}` sigue
disponible, incluyendo los resultados `COMPLETED`, `FAILED` y `SKIPPED`.

La tarea usa seguimiento STARTED, ACK tardío, prefetch 1, límite suave de
840 segundos y duro de 900; la visibilidad Redis es de 1800 segundos.
`max_retries=3` significa **tres reintentos además del intento inicial** (cuatro
intentos máximos): backoff 5, 10 y 20 segundos solo para fallos transitorios
de conexión, pool, serialización, deadlock o timeout de PostgreSQL. Los reintentos
internos de las tareas Prefect previas se conservan. Los fallos permanentes van
a DLQ inmediatamente; al agotarse los reintentos también se guarda una entrada
única en `task_dead_letters` con UUID, intento (1–4), error sanitizado y timestamp.
Los rechazos de publicación (intento 0) no son tareas ejecutadas ni entradas DLQ.
La reentrega de una tarea completada devuelve su resultado persistido; el contador
duradero impide ejecutar un quinto intento incluso después de una caída del worker; la
idempotencia de UPSERT y el advisory lock del pipeline se conservan.

Los logs registran duración, intento y estado sin texto libre de excepciones ni
credenciales. Ante indisponibilidad de PostgreSQL, el worker rechaza y reencola
la entrega para evitar confirmar una DLQ que no pudo persistir. Redis AOF con
`everysec` puede perder hasta aproximadamente un segundo de escrituras ante una
caída abrupta del host: esta configuración es para desarrollo, no una garantía
de entrega exactamente una vez ni un outbox transaccional.

Ejecuta la demostración real aislada (Docker Compose ≥2.24.4):

```bash
python scripts/demo_async_tasks.py
```

La demo crea su propio PostgreSQL, usuarios, Redis, API, worker y Flower, sin usar
la base operativa. Publica con el worker detenido, comprueba el mensaje UUID-only,
detiene la API y termina el pipeline real desde el worker. Luego provoca un error
**real** PostgreSQL `40001` mediante un wrapper exclusivo de demo
(`scripts/demo_async_worker.py`) para verificar backoff, cuatro intentos, DLQ y
Flower FAILURE. Comprueba Flower SUCCESS y el `503` con Redis apagado. Genera
evidencias en `docs/pr-assets/dev55/` y retira únicamente su proyecto y volúmenes.
Ese wrapper no se utiliza en el worker normal. Puertos temporales: 18055 (API),
16355 (Redis), 15555 (Flower). No se añaden dependencias Python para la demo.

Pruebas (usa exclusivamente una base PostgreSQL de pruebas):

```bash
PYTHONPATH=services/api:. SUPPLIERS_DB_PATH=/tmp/brasaland-tests-users.json \
  TEST_DATABASE_URL="$TEST_DATABASE_URL" \
  services/api/.venv/bin/python -m pytest services/api/tests tests/pipelines tests/scripts -q
```

Capturas opcionales de Flower en navegador real (Playwright fuera del repo):

```bash
npm install --prefix /tmp/dev55-browser playwright
/tmp/dev55-browser/node_modules/.bin/playwright install chromium
DEV55_PLAYWRIGHT_MODULE=/tmp/dev55-browser/node_modules/playwright \
  python scripts/demo_async_tasks.py
```
