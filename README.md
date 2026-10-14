# AI Engineering Company Project — Student Template

[![4Geeks Academy](https://img.shields.io/badge/4Geeks-Academy-blue)](https://4geeksacademy.com)
[![AI Engineering](https://img.shields.io/badge/track-AI%20Engineering-green)](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)

_Base template for transversal projects in the AI Engineering Career Program — 4Geeks Academy._

> _Instrucciones disponibles en español en [README.es.md](./README.es.md)._

---

## Purpose

This repository is the **starter template** for transversal projects. You will work on real company scenarios (Brasaland, TrackFlow, Nexova), building deliverables that map to course milestones (Web, Programming, Backend, Telemetry, RAG, Agents, Workflows, Real-time).

- Create a template from this repository.
- Replace the placeholder `CONTEXT.md` with your assigned company context.
- Use `skills/` and the directory-level `README.md` files as working guidance.

---

## Current status of the template

The repository currently provides a **base folder structure and documentation skeleton**. It does not include runnable apps or global scripts yet.

- `CONTEXT.md` is a placeholder and must be replaced with your assigned company context.
- There is no root `AGENTS.md` yet.
- Shared package metadata exists in `packages/shared/package.json` (`@repo/shared-types`), but no workspace runner is configured at root.

---

## Repository structure

```text
ai-engineering-company-project-monorepo/
├── README.md
├── README.es.md
├── CONTEXT.md                # Placeholder to be replaced with assigned context
├── agents/                   # Agent patterns/templates and tools docs
├── data/                     # raw, process, pipelines, eval
├── docs/                     # Project and architecture documentation
├── infra/                    # Docker, Terraform, deployment configs
├── internal/                 # CLIs, packaged migration scripts, internal utilities
├── mcps/                     # Model Context Protocol (MCP) Servers
├── packages/
│   └── shared/               # Shared package (@repo/shared-types)
├── scripts/                  # Script conventions/documentation
├── services/                 # APIs and background workers
├── shared/                   # Shared assets/conventions at repo level
├── skills/                   # Reusable agent skills
├── uis/                      # User interfaces (React, Next.js, Streamlit, HTML)
└── workflows/                # Automation/orchestration documentation
```

---

## Docker Development Environment

The entire development stack can be started with a single Docker Compose command from the repository root:

```bash
# 1. Prepare environment variables
cp .env.example .env
# Edit .env with your accessible PostgreSQL DATABASE_URL and SECRET_KEY

# 2. Build and start services
docker compose up --build
```

### Services and Ports

| Service | Technology | Internal Port | Published Port | Description |
|---|---|---|---|---|
| `interfaces` | Next.js 16 (Node 22 Alpine) | 3000, 3001 | `http://localhost:3000`<br>`http://localhost:3001` | Single container running Website (3000) and Backoffice (3001) |
| `backend` | FastAPI (Python 3.12 Slim, uv) | 8000 | `http://localhost:8000` | Operations, inventory, auth, and analytics API (`/health`, `/docs`) |

### Key Characteristics

- **Internal Networking**: Services communicate over the `brasaland-dev` bridge network using Docker service hostnames (`http://backend:8000`).
- **Client Proxy Rewrites**: The browser communicates with `/api/*` through Next.js server-side rewrites targeting `INTERNAL_API_URL`.
- **Hot Reload**: Live code changes in `uis/` and `services/` trigger instant reloads via bind mounts without rebuilding containers.
- **Stop Services Safely**:
  ```bash
  docker compose down
  ```
  *(Avoid `docker compose down -v` to prevent accidental volume deletion).*

---

## Milestones (reference)

| Milestone | Focus        | Typical deliverables                        |
| --------- | ------------ | ------------------------------------------- |
| 0         | Prework      | Environment setup, first prompts            |
| 1         | Web          | Corporate website, forms, SEO               |
| 2         | Programming  | Business logic, scoring, calculations       |
| 3         | AI-driven UI | AI-generated interfaces                     |
| 4         | Next.js      | Portals, loyalty app, operations UI         |
| 5         | Backend      | Central API (locations, menus, sales, etc.) |
| 6         | Telemetry    | Data pipeline, dashboards                   |
| 7         | RAG & Memory | Semantic knowledge base, search             |
| 8         | Agents       | Support, onboarding, training agents        |
| 9         | Workflows    | n8n automations                             |
| 10        | Real-time    | Live dashboards, alerts, streaming          |

---

## Links

- [4Geeks Academy — AI Engineering](https://4geeksacademy.com/es/programas-de-carrera/ingenieria-ia)
- [How to start a coding project](https://4geeks.com/lesson/how-to-start-a-project)

---

## Contributors

This template was built as part of the 4Geeks Academy AI Engineering Career Program by [@marcogonzalo](https://www.linkedin.com/in/marcogonzalo) and [@alezanchezr](https://x.com/alesanchezr) and many other contributors. Find out more about our [AI Engineering Course](https://4geeksacademy.com/en/career-programs/ai-engineering), and [other courses](https://4geeksacademy.com/en/program-comparison).

You can find other templates and resources like this at the [4Geeks Academy GitHub page](https://github.com/4geeksacademy).

_This template is maintained by 4Geeks Academy for the AI Engineering track. For exclusive use in the programme._
# DEV-55: asynchronous inventory health runs

`POST /reporting/inventory-health/runs` keeps its admin/manager authorization and
existing response fields, adding `task_id` equal to `flow_run_id`. Only that UUID
is sent through Redis. A separate Celery worker imports the existing Prefect
pipeline and retrieves inputs from PostgreSQL. The nightly CLI, cron and
`job_runs` are unchanged.

Set `DATABASE_URL`, `SECRET_KEY`, `REDIS_URL=redis://redis:6379/0` and your own
local `FLOWER_BASIC_AUTH=user:password` in `.env`. Apply the existing reporting
migrations and `services/api/migrations/004_create_async_tasks.sql`; API
`init_db()` also registers the new tracking/DLQ tables.

```bash
docker compose up -d --build redis backend worker
docker compose --profile monitoring up -d --build flower
docker compose logs -f worker
docker compose --profile monitoring stop backend worker flower redis
docker compose --profile monitoring down  # preserves persistent volumes
```

Redis uses AOF, `appendfsync everysec`, persistent storage and `noeviction`,
binding port 6379 to localhost. Flower requires Basic authentication, uses the
opt-in `monitoring` profile, persists its events and binds port 5555 to localhost.
Keep Codespaces port forwarding private. The Python image builds from the repo
root and includes `data/pipelines/`, so both API and worker can import it.

Authenticated `GET /tasks/{task_id}` returns `{task_id, status, result}` with
`pending`, `started`, `success` or `failure`. Unknown UUIDs return 404; terminal
results older than 24 hours return 410. Persistent tracking distinguishes a
genuine pending task from Celery's generic PENDING response and retains terminal
results if the Redis key disappears. Broker publication errors return 503 and
mark the scheduled flow FAILED. The existing reporting run-status GET remains.

Tasks track STARTED, ACK late, prefetch one message, and use 840/900-second
soft/hard limits with a 1800-second Redis visibility timeout. `max_retries=3`
means **three retries plus the initial attempt**, using 5/10/20-second exponential
backoff only for transient errors. Existing Prefect retries are preserved.
Permanent or exhausted failures create one durable `task_dead_letters` row with
UUID, attempt, sanitized error and timestamp. Publication failures (attempt 0)
do not enter the execution DLQ. Completed redeliveries reuse their saved result; a durable attempt counter prevents
a fifth business execution even after worker loss;
the pipeline's advisory lock and UPSERT idempotency remain in force. Logs contain
duration, attempt and state without credentials or raw exceptions. When durable
storage is unavailable, the worker requeues rather than acknowledging a missing
DLQ entry. AOF `everysec` can lose about one second of writes on abrupt host loss;
this development setup does not claim exactly-once delivery or a transactional
outbox.

Run the real isolated demo (Docker Compose ≥2.24.4):

```bash
python scripts/demo_async_tasks.py
```

It provisions its own PostgreSQL, Redis, users and containers, verifies a fast
202 and UUID-only message while the worker is stopped, then stops the API while
the worker completes the real pipeline. A demo-only wrapper executes a real
PostgreSQL SQLSTATE 40001 error to demonstrate retries, the fourth failed attempt,
DLQ and Flower FAILURE alongside SUCCESS. It also checks 503 with Redis stopped.
Evidence is saved under `docs/pr-assets/dev55/`; only demo resources are removed.
Temporary ports: API 18055, Redis 16355, Flower 15555. The normal worker never
loads the fault-injection wrapper. See [Spanish instructions](README.es.md) for
the full retry policy and test command.

For optional real-browser Flower screenshots, install Playwright outside the repo
(e.g. `/tmp/dev55-browser`) and its Chromium browser, then run the demo with
`DEV55_PLAYWRIGHT_MODULE=/tmp/dev55-browser/node_modules/playwright`.
