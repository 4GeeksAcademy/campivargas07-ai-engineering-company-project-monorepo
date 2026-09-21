"""service.py — Brasaland · Lógica de negocio de Locales"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.domains.locations.models import Local
from app.domains.locations.schemas import LocalCreate, LocalUpdate

# Regla de negocio Brasaland: la moneda depende del país de operación
MONEDA_POR_PAIS = {"CO": "COP", "US": "USD"}


class LocalService:
    @staticmethod
    def listar(
        db: Session, *, page: int = 1, size: int = 20, pais: str | None = None
    ) -> tuple[list[Local], int]:
        query = db.query(Local)
        if pais:
            query = query.filter(Local.pais == pais.upper())
        total = query.count()
        items = query.order_by(Local.nombre).offset((page - 1) * size).limit(size).all()
        return items, total

    @staticmethod
    def obtener(db: Session, local_id: int) -> Local | None:
        return db.get(Local, local_id)

    @staticmethod
    def crear(db: Session, data: LocalCreate) -> Local:
        # Regla de negocio: moneda coherente con el país (CO→COP, US→USD)
        data = data.model_copy(update={"moneda": MONEDA_POR_PAIS[data.pais]})
        obj = Local(**data.model_dump())
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def actualizar(db: Session, local_id: int, data: LocalUpdate) -> Local | None:
        obj = db.get(Local, local_id)
        if obj is None:
            return None
        cambios = data.model_dump(exclude_unset=True)
        # Si cambia el país, la moneda se recalcula con la regla de negocio
        if "pais" in cambios and cambios["pais"]:
            cambios["moneda"] = MONEDA_POR_PAIS[cambios["pais"]]
        for campo, valor in cambios.items():
            setattr(obj, campo, valor)
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def eliminar(db: Session, local_id: int) -> bool:
        """Borrado físico; la FK en cascada limpia inventario y vínculos N:M."""
        obj = db.get(Local, local_id)
        if obj is None:
            return False
        db.delete(obj)
        db.commit()
        return True