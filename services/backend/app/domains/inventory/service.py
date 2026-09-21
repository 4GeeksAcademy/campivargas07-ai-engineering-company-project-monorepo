"""service.py — Brasaland · Lógica de negocio de Inventario

Núcleo del hito: registrar_movimiento() ejecuta en UNA SOLA transacción
la actualización de stock + la inserción del Kardex. Si algo falla,
rollback completo — el stock nunca queda inconsistente con el historial.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domains.ingredients.models import (
    Ingrediente,
    InventarioLocal,
    MovimientoInventario,
)
from app.domains.locations.models import Local
from app.domains.inventory.schemas import AlertaInventarioOut, MovimientoCreate


class InventarioError(ValueError):
    """Error de regla de negocio de inventario (→ HTTP 400)."""


class InventarioService:
    @staticmethod
    def _obtener_o_crear_inventario(
        db: Session, local_id: int, ingrediente_id: int
    ) -> InventarioLocal:
        """Obtiene el registro de inventario (local, ingrediente); lo crea si no existe."""
        inv = (
            db.query(InventarioLocal)
            .filter(
                InventarioLocal.local_id == local_id,
                InventarioLocal.ingrediente_id == ingrediente_id,
            )
            .first()
        )
        if inv is None:
            # Validar que existan local e ingrediente antes de crear el registro
            if not db.get(Local, local_id):
                raise InventarioError(f"El local {local_id} no existe")
            if not db.get(Ingrediente, ingrediente_id):
                raise InventarioError(f"El ingrediente {ingrediente_id} no existe")
            inv = InventarioLocal(
                local_id=local_id, ingrediente_id=ingrediente_id, cantidad_actual=Decimal("0"),
                cantidad_minima=Decimal("0"),
            )
            db.add(inv)
            db.flush()  # asigna PK sin cerrar la transacción
        return inv

    @staticmethod
    def registrar_movimiento(
        db: Session, data: "MovimientoCreateLike"
    ) -> InventarioLocal:
        """Transacción atómica: valida → aplica efecto en stock → inserta Kardex.

        Reglas:
        - entrada  → cantidad_actual += cantidad
        - salida   → cantidad_actual -= cantidad (400 si dejaría stock negativo)
        - ajuste   → cantidad_actual = cantidad (conteo físico)
        """
        inv = InventarioService._obtener_o_crear_inventario(db, data.local_id, data.ingrediente_id)

        if data.tipo == "entrada":
            inv.cantidad_actual += data.cantidad
        elif data.tipo == "salida":
            if inv.cantidad_actual < data.cantidad:
                raise InventarioError(
                    f"Stock insuficiente: hay {inv.cantidad_actual} "
                    f"{inv.ingrediente.unidad if inv.ingrediente else ''} y se "
                    f"intentan retirar {data.cantidad}"
                )
            inv.cantidad_actual -= data.cantidad
        else:  # ajuste
            inv.cantidad_actual = data.cantidad

        mov = MovimientoInventario(
            inventario_local_id=inv.id,
            tipo=data.tipo,
            cantidad=data.cantidad,
            motivo=data.motivo,
        )
        db.add(mov)
        db.commit()  # ← commit ÚNICO: stock e historial quedan consistentes
        db.refresh(inv)
        db.refresh(mov)
        return inv

    @staticmethod
    def listar_stock(
        db: Session,
        *,
        local_id: int | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[InventarioLocal], int]:
        query = db.query(InventarioLocal)
        if local_id:
            query = query.filter(InventarioLocal.local_id == local_id)
        total = query.count()
        items = (
            query.order_by(InventarioLocal.local_id, InventarioLocal.ingrediente_id)
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )
        return items, total

    @staticmethod
    def alertas(db: Session, *, local_id: int | None = None) -> list[AlertaInventarioOut]:
        """Ingredientes con stock por debajo (o igual) del mínimo por local.

        Es el corazón del problema de negocio de Brasaland: detectar
        quiebres de stock antes de que ocurran.
        """
        query = (
            db.query(
                InventarioLocal.id.label("inventario_id"),
                Local.id.label("local_id"),
                Local.nombre.label("local_nombre"),
                Local.ciudad.label("local_ciudad"),
                Local.pais.label("pais"),
                Ingrediente.id.label("ingrediente_id"),
                Ingrediente.codigo.label("ingrediente_codigo"),
                Ingrediente.nombre.label("ingrediente_nombre"),
                Ingrediente.unidad.label("unidad"),
                InventarioLocal.cantidad_actual,
                InventarioLocal.cantidad_minima,
            )
            .join(Local, InventarioLocal.local_id == Local.id)
            .join(Ingrediente, InventarioLocal.ingrediente_id == Ingrediente.id)
            .filter(InventarioLocal.cantidad_actual <= InventarioLocal.cantidad_minima)
        )
        if local_id:
            query = query.filter(InventarioLocal.local_id == local_id)

        rows = query.order_by(InventarioLocal.cantidad_actual).all()
        return [
            AlertaInventarioOut(
                inventario_id=row.inventario_id,
                local_id=row.local_id,
                local_nombre=row.local_nombre,
                local_ciudad=row.local_ciudad,
                pais=row.pais,
                ingrediente_id=row.ingrediente_id,
                ingrediente_codigo=row.ingrediente_codigo,
                ingrediente_nombre=row.ingrediente_nombre,
                cantidad_actual=row.cantidad_actual,
                cantidad_minima=row.cantidad_minima,
                deficit=row.cantidad_minima - row.cantidad_actual,
            )
            for row in rows
        ]

    @staticmethod
    def movimientos_de_inventario(
        db: Session, inventario_local_id: int, *, limite: int = 50
    ) -> list[MovimientoInventario]:
        """Kardex: últimos movimientos de un registro de inventario."""
        return (
            db.query(MovimientoInventario)
            .filter(MovimientoInventario.inventario_local_id == inventario_local_id)
            .order_by(MovimientoInventario.created_at.desc())
            .limit(limite)
            .all()
        )