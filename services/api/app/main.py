import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import backfill_users_uuid, init_db
from app.domains.analytics.incidents.router import router as analytics_incidents_router
from app.domains.auth.router import router as auth_router
from app.domains.incidents.errors import register_incident_error_handlers
from app.domains.incidents.router import router as incidents_router
from app.domains.operations.inventory.router import router as inventory_router
from app.domains.procurement.suppliers.router import router as suppliers_router
from app.domains.profiles.router import router as profiles_router
from app.domains.telemetry.router import router as telemetry_router
from app.domains.users.router import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup & shutdown events."""
    # Backfill stable UUIDs for any existing TinyDB users
    backfill_users_uuid()
    # Initialize SQLModel PostgreSQL tables if DATABASE_URL is configured
    if os.environ.get("DATABASE_URL"):
        init_db()
    yield


app = FastAPI(
    title="Brasaland API",
    description="Internal API for Brasaland operations: inventory, suppliers, auth, incidents.",
    version="0.5.0",
    lifespan=lifespan,
)

register_incident_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3002",
        "http://127.0.0.1:3002",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Domain Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)
app.include_router(analytics_incidents_router)
app.include_router(incidents_router)
app.include_router(inventory_router)
app.include_router(telemetry_router)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
