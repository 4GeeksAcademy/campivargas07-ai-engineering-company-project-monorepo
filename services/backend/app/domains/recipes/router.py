"""router.py — Brasaland · Endpoints MongoDB (recetas y auditoría)

- POST /api/v1/recetas            → inserta documento anidado (201)
- GET  /api/v1/recetas            → lista con filtro opcional por categoría
- GET  /api/v1/recetas/{id}       → obtiene por _id (ObjectId → str)
- GET  /api/v1/recetas/buscar     → búsqueda flexible por nombre de plato
- GET  /api/v1/auditoria          → últimos logs de auditoría (sistema)
Escritura protegida con JWT.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from bson import ObjectId

from app.common.security import get_current_user
from app.domains.auth.models import Usuario
from app.domains.recipes.repository import (
    AuditoriaRepository,
    RecetasRepository,
    _es_object_id_valido,
)
from app.domains.recipes.schemas import AuditoriaLogOut, RecetaCreate, RecetaOut

router = APIRouter(prefix="/api/v1", tags=["recetas-mongo"])


def _a_receta_out(doc: dict) -> RecetaOut:
    """Convierte un documento Mongo a schema (ObjectId → str)."""
    doc = dict(doc)
    doc["_id"] = str(doc["_id"])
    return RecetaOut.model_validate(doc)


@router.post("/recetas", response_model=RecetaOut, status_code=status.HTTP_201_CREATED)
def crear_receta(
    payload: RecetaCreate,
    _: Usuario = Depends(get_current_user),
) -> RecetaOut:
    """Inserta una receta con ingredientes y pasos anidados (documento flexible).

    Además escribe un log de auditoría en la colección auditoria_logs.
    """
    result = RecetasRepository.crear(payload)
    AuditoriaRepository.insertar(
        {
            "entidad": "receta",
            "entidad_id": str(result.inserted_id),
            "accion": "crear",
            "usuario": "api",
            "detalle": {"plato": payload.plato, "ingredientes": len(payload.ingredientes)},
        }
    )
    doc = RecetasRepository.obtener(str(result.inserted_id))
    return _a_receta_out(doc)


@router.get("/recetas", response_model=list[RecetaOut])
def listar_recetas(
    categoria: str | None = Query(None, examples=["carnes"]),
    limit: int = Query(20, ge=1, le=100),
) -> list[RecetaOut]:
    """Lista recetas de MongoDB con filtro opcional por categoría."""
    return [_a_receta_out(d) for d in RecetasRepository.listar(categoria=categoria, limit=limit)]


@router.get("/recetas/buscar", response_model=list[RecetaOut])
def buscar_recetas(
    plato: str = Query(..., min_length=2, max_length=80, examples=["churrasco"]),
) -> list[RecetaOut]:
    """Búsqueda flexible por nombre de plato (regex, insensible a mayúsculas)."""
    docs = RecetasRepository.buscar_por_plato(plato)
    return [_a_receta_out(d) for d in docs]


@router.get("/recetas/{receta_id}", response_model=RecetaOut)
def obtener_receta(receta_id: str) -> RecetaOut:
    """Obtiene una receta por su _id de MongoDB (24 hex chars)."""
    if not _es_object_id_valido(receta_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "_id de MongoDB inválido")
    doc = RecetasRepository.obtener(receta_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Receta no encontrada")
    return _a_receta_out(doc)


@router.get("/auditoria", response_model=list[AuditoriaLogOut])
def ultimos_logs(
    limite: int = Query(20, ge=1, le=100),
    _: Usuario = Depends(get_current_user),
) -> list[AuditoriaLogOut]:
    """Últimos eventos de auditoría registrados en MongoDB (requiere token)."""
    docs = AuditoriaRepository.ultimos(limite)
    out = []
    for d in docs:
        d = dict(d)
        d["_id"] = str(d["_id"])
        # created_at se deriva del timestamp embebido en el ObjectId (4 bytes iniciales)
        if d.get("created_at") is None:
            d["created_at"] = ObjectId(d["_id"]).generation_time.isoformat()
        out.append(AuditoriaLogOut.model_validate(d))
    return out