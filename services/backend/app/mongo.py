"""mongo.py — Brasaland · Cliente MongoDB (pymongo)

Gestiona el cliente y las colecciones del servicio:
- ``recetas``          → documentos anidados con esquema variable (pasos, ingredientes, versiones)
- ``auditoria_logs``   → registro de operaciones de escritura (patrón de logs de auditoría)

La conexión se crea en el lifespan de FastAPI (main.py) y se cierra al apagar.
"""
from __future__ import annotations

import logging
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.config import settings

logger = logging.getLogger(__name__)

_client: MongoClient[Any] | None = None
_db: Any = None

# Nombres de colecciones (fuente única de verdad)
RECETAS_COLLECTION = "recetas"
AUDITORIA_COLLECTION = "auditoria_logs"


def connect_mongo() -> None:
    """Abre la conexión y verifica que el servidor responde (ping)."""
    global _client, _db
    _client = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    _db = _client[settings.mongo_db]
    _client.admin.command("ping")
    logger.info("MongoDB conectado: %s", settings.mongo_host)


def close_mongo() -> None:
    """Cierra la conexión al apagar la aplicación."""
    global _client, _db
    if _client:
        _client.close()
    _client, _db = None, None
    logger.info("MongoDB desconectado")


def get_mongo_db() -> Any:
    """Devuelve la base de datos activa (lanza error claro si no se conectó)."""
    if _db is None:
        raise RuntimeError("MongoDB no está conectado. ¿Se ejecutó connect_mongo()?")
    return _db


def get_recetas_collection() -> Any:
    """Colección de recetas (documentos flexibles y anidados)."""
    return get_mongo_db()[RECETAS_COLLECTION]


def get_auditoria_collection() -> Any:
    """Colección de logs de auditoría."""
    return get_mongo_db()[AUDITORIA_COLLECTION]


def mongo_health() -> bool:
    """Healthcheck simple para /health."""
    try:
        if _client is None:
            return False
        _client.admin.command("ping")
        return True
    except PyMongoError:
        return False