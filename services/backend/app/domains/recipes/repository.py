"""repository.py — Brasaland · Acceso a MongoDB (pymongo)

Aísla las queries de MongoDB del resto del dominio:
- recetas: documentos anidados y flexibles
- auditoria_logs: inserción rápida de eventos
"""
from __future__ import annotations

from typing import Any

from app import mongo
from app.domains.recipes.schemas import RecetaCreate

RECETAS = mongo.RECETAS_COLLECTION
AUDITORIA = mongo.AUDITORIA_COLLECTION


class RecetasRepository:
    @staticmethod
    def crear(data: RecetaCreate) -> Any:
        """Inserta el documento y devuelve el resultado (incluye inserted_id)."""
        coleccion = mongo.get_recetas_collection()
        return coleccion.insert_one(data.model_dump(by_alias=True, exclude_none=True))

    @staticmethod
    def listar(categoria: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        query: dict[str, Any] = {"categoria": categoria} if categoria else {}
        return list(mongo.get_recetas_collection().find(query).limit(limit))

    @staticmethod
    def buscar_por_plato(plato: str) -> list[dict[str, Any]]:
        """Búsqueda textual flexible sobre el nombre del plato (regex insensible)."""
        import re

        return list(
            mongo.get_recetas_collection()
            .find({"plato": {"$regex": re.escape(plato), "$options": "i"}})
            .limit(20)
        )

    @staticmethod
    def obtener(doc_id: str) -> dict[str, Any] | None:
        from bson import ObjectId

        if not _es_object_id_valido(doc_id):
            return None
        return mongo.get_recetas_collection().find_one({"_id": ObjectId(doc_id)})

    @staticmethod
    def contar() -> int:
        return mongo.get_recetas_collection().count_documents({})


class AuditoriaRepository:
    @staticmethod
    def insertar(evento: dict[str, Any]) -> Any:
        return mongo.get_auditoria_collection().insert_one(evento)

    @staticmethod
    def ultimos(limite: int = 20) -> list[dict[str, Any]]:
        return list(
            mongo.get_auditoria_collection()
            .find()
            .sort("_id", -1)  # ObjectId ordena por fecha de inserción
            .limit(limite)
        )


def _es_object_id_valido(valor: str) -> bool:
    from bson import ObjectId

    try:
        ObjectId(valor)
        return True
    except Exception:
        return False