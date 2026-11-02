import os
import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.common.timing import RequestTimingMiddleware
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
from app.domains.knowledge.router import router as knowledge_router
from app.domains.agent.router import router as agent_router
from app.domains.rfp.router import router as rfp_router
from app.domains.chat.router import router as chat_router
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


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

# ── Request timing middleware ────────────────────────────────
# Logs: method, route path, status code and duration (ms) via logging.
# Never logs query strings, headers or bodies (no sensitive data).
app.add_middleware(RequestTimingMiddleware)
register_incident_error_handlers(app)

# CORS: origins can be configured; defaults are local development only.
_cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        # HSTS only when the deployment is known to be HTTPS.
        if os.environ.get("ENABLE_HSTS", "").lower() == "true":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


# Simple in-memory rate limiting for sensitive endpoints.
_RATE_LIMITS: dict[str, deque[float]] = defaultdict(deque)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if os.environ.get("BRASALAND_ENV", "").lower() in {"test"}:
            return await call_next(request)
        path = request.url.path
        limit = None
        window = 60.0
        if path.endswith("/auth/login"):
            limit = int(os.environ.get("RATE_LIMIT_LOGIN_PER_MINUTE", "10"))
        elif path.startswith("/telemetry/events"):
            limit = int(os.environ.get("RATE_LIMIT_TELEMETRY_PER_MINUTE", "60"))
        if limit is not None:
            client = request.client.host if request.client else "unknown"
            key = f"{client}:{path}"
            now = time.monotonic()
            bucket = _RATE_LIMITS[key]
            while bucket and now - bucket[0] > window:
                bucket.popleft()
            if len(bucket) >= limit:
                from fastapi.responses import JSONResponse

                return JSONResponse({"detail": "Too many requests"}, status_code=429)
            bucket.append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Domain Routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
app.include_router(suppliers_router)
app.include_router(analytics_incidents_router)
app.include_router(incidents_router)
app.include_router(inventory_router)
app.include_router(telemetry_router)
app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(rfp_router)
app.include_router(chat_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def healthcheck() -> HealthResponse:
    return HealthResponse(status="ok")
