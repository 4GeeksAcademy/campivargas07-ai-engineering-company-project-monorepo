"""main.py — Brasaland Backend · Punto de entrada FastAPI

Monta los routers por dominio y gestiona el ciclo de vida de MongoDB
(lifespan: connect_mongo al arrancar, close_mongo al apagar).

Ejecución local:
    uv run uvicorn app.main:app --reload --port 8001
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import mongo
from app.config import settings
from app.domains.ingredients.router import router as ingredientes_router
from app.domains.locations.router import router as locales_router
from app.domains.procurement.router import router as proveedores_router

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida: conecta MongoDB al arrancar y lo cierra al apagar."""
    mongo.connect_mongo()
    yield
    mongo.close_mongo()


app = FastAPI(
    title="Brasaland Backend API",
    description=(
        "API de gestión de inventario de Brasaland (14 locales, Colombia y Florida).\n\n"
        "**PostgreSQL** (SQLAlchemy + Alembic): locales, ingredientes, inventario y proveedores.\n\n"
        "**MongoDB** (pymongo): recetas con documentos anidados y logs de auditoría."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

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

# Routers por dominio (cada uno con su prefijo /api/v1/...)
app.include_router(locales_router)
app.include_router(ingredientes_router)
app.include_router(proveedores_router)


@app.get("/health", tags=["health"])
def healthcheck() -> dict[str, str]:
    """Healthcheck general: verifica la conexión a MongoDB."""
    return {
        "status": "ok",
        "mongo": "up" if mongo.mongo_health() else "down",
        "service": "brasaland-backend",
        "environment": settings.postgres_db,
    }