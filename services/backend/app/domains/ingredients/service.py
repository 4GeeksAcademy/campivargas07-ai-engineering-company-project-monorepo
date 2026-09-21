"""service.py — Brasaland · Lógica de negocio de Ingredientes

Reglas que NO deben vivir en el router:
- unicidad de código (400 si se duplica)
- FK de proveedor válida (400 si no existe)
- borrado lógico: un ingrediente con inventario no se elimina físicamente
  (protege el historial de movimientos — integridad referencial)
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.ingredients.models import Ingrediente
from app.domains.ingredients.schemas import IngredienteCreate, IngredienteUpdate
from app.domains.inventory.models import InventarioLocal
from app.domains.procurement.models import Proveedor


class IngredienteService:
    """Operaciones de negocio sobre ingredientes."""

    @staticmethod
    def listar(
        db: Session,
        *,
        page: int = 1,
        size: int = 20,
        activo: bool | None = None,
        proveedor_id: int | None = None,
        search: str | None = None,
    ) -> tuple[list[Ingrediente], int]:
        """Lista paginada con filtros opcionales. Devuelve (items, total)."""
        query = db.query(Ingrediente)
        if activo is not None:
            query = query.filter(Ingrediente.activo == activo)
        if proveedor_id is not None:
            query = query.filter(Ingrediente.proveedor_id == proveedor_id)
        if search:
            patron = f"%{search.lower()}%"
            query = query.filter(
                (Ingrediente.nombre.ilike(patron)) | (Ingrediente.codigo.ilike(patron))
            )
        total = query.count()
        items = (
            query.order_by(Ingrediente.codigo)
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    @staticmethod
    def obtener(db: Session, ingrediente_id: int) -> Ingrediente | None:
        return db.get(Ingrediente, ingrediente_id)

    @staticmethod
    def crear(db: Session, data: IngredienteCreate) -> Ingrediente:
        # Regla 1: código único
        if db.query(Ingrediente).filter(Ingrediente.codigo == data.codigo).first():
            raise ValueError(f"El código '{data.codigo}' ya existe")
        # Regla 2: proveedor debe existir si se envía
        if data.proveedor_id is not None:
            if not db.get(Proveedor, data.proveedor_id):
                raise ValueError(f"El proveedor {data.proveedor_id} no existe")
        obj = Ingrediente(**data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def actualizar(
        db: Session, ingrediente_id: int, data: IngredienteUpdate
    ) -> Ingrediente | None:
        obj = db.get(Ingrediente, ingrediente_id)
        if obj is None:
            return None
        cambios = data.model_dump(exclude_unset=True)
        if "proveedor_id" in cambios and cambios["proveedor_id"] is not None:
            if not db.get(Proveedor, cambios["proveedor_id"]):
                raise ValueError(f"El proveedor {cambios['proveedor_id']} no existe")
        for campo, valor in cambios.items():
            setattr(obj, campo, valor)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def eliminar(db: Session, ingrediente_id: int) -> tuple[bool, bool]:
        """Elimina un ingrediente.

        Devuelve (encontrado, borrado_logico):
        - Si tiene inventario asociado → borrado lógico (activo=False)
        - Si no tiene inventario → borrado físico
        """
        obj = db.get(Ingrediente, ingrediente_id)
        if obj is None:
            return False, False
        tiene_inventario = (
            db.query(InventarioLocal)
            .filter(InventarioLocal.ingrediente_id == ingrediente_id)
            .first()
            is not None
        )
        if tiene_inventario:
            obj.activo = False  # borrado lógico: preserva movimientos históricos
            db.commit()
            return True, True
        db.delete(obj)
        db.commit()
        return True, False