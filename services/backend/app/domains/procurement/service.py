"""service.py — Brasaland · Lógica de negocio de Proveedores (y N:M con locales)"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.locations.models import Local
from app.domains.procurement.models import LocalProveedor, Proveedor
from app.domains.procurement.schemas import LocalProveedorCreate, ProveedorCreate, ProveedorUpdate


class ProveedorError(ValueError):
    """Error de regla de negocio (→ HTTP 400)."""


class ProveedorService:
    @staticmethod
    def listar(
        db: Session, *, page: int = 1, size: int = 20, pais: str | None = None
    ) -> tuple[list[Proveedor], int]:
        query = db.query(Proveedor)
        if pais:
            query = query.filter(Proveedor.pais == pais.upper())
        total = query.count()
        items = query.order_by(Proveedor.nombre).offset((page - 1) * size).limit(size).all()
        return items, total

    @staticmethod
    def obtener(db: Session, proveedor_id: int) -> Proveedor | None:
        return db.get(Proveedor, proveedor_id)

    @staticmethod
    def crear(db: Session, data: ProveedorCreate) -> Proveedor:
        if db.query(Proveedor).filter(Proveedor.nombre == data.nombre).first():
            raise ProveedorError(f"Ya existe un proveedor llamado '{data.nombre}'")
        obj = Proveedor(**data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def actualizar(
        db: Session, proveedor_id: int, data: ProveedorUpdate
    ) -> Proveedor | None:
        obj = db.get(Proveedor, proveedor_id)
        if obj is None:
            return None
        cambios = data.model_dump(exclude_unset=True)
        if "nombre" in cambios and cambios["nombre"]:
            dup = (
                db.query(Proveedor)
                .filter(Proveedor.nombre == cambios["nombre"], Proveedor.id != proveedor_id)
                .first()
            )
            if dup:
                raise ProveedorError(f"Ya existe un proveedor llamado '{cambios['nombre']}'")
        for campo, valor in cambios.items():
            setattr(obj, campo, valor)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def eliminar(db: Session, proveedor_id: int) -> bool:
        obj = db.get(Proveedor, proveedor_id)
        if obj is None:
            return False
        db.delete(obj)
        db.commit()
        return True

    # --- N:M locales ↔ proveedores ---

    @staticmethod
    def vincular_local(
        db: Session, local_id: int, proveedor_id: int, data: LocalProveedorCreate
    ) -> LocalProveedor:
        """Vincula un proveedor a un local (tabla intermedia con atributos)."""
        if not db.get(Local, local_id):
            raise ProveedorError(f"El local {local_id} no existe")
        proveedor = db.get(Proveedor, proveedor_id)
        if proveedor is None:
            raise ProveedorError(f"El proveedor {proveedor_id} no existe")
        existente = (
            db.query(LocalProveedor)
            .filter(
                LocalProveedor.local_id == local_id,
                LocalProveedor.proveedor_id == proveedor_id,
            )
            .first()
        )
        if existente:
            raise ProveedorError(
                f"El proveedor {proveedor_id} ya está vinculado al local {local_id}"
            )
        vinculo = LocalProveedor(
            local_id=local_id, proveedor_id=proveedor_id, **data.model_dump()
        )
        db.add(vinculo)
        db.commit()
        db.refresh(vinculo)
        return vinculo

    @staticmethod
    def locales_del_proveedor(db: Session, proveedor_id: int) -> list[LocalProveedor]:
        """Locales atendidos por un proveedor (con condiciones comerciales)."""
        return (
            db.query(LocalProveedor)
            .filter(LocalProveedor.proveedor_id == proveedor_id)
            .all()
        )