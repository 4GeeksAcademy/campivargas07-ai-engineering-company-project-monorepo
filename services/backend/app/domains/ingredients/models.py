"""models.py — Brasaland · Modelos de Ingredientes e Inventario

- ``Ingrediente``          → catálogo global (código único, unidad, costos, stock mínimo)
- ``InventarioLocal``      → stock de un ingrediente en un local (relación 1:N con Local)
- ``MovimientoInventario`` → historial de entradas/salidas/ajustes (Kardex)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.locations.models import Local
    from app.domains.procurement.models import Proveedor

UnidadEnum = Enum("kg", "g", "L", "ml", "unidad", name="unidad_enum")
TipoMovimientoEnum = Enum("entrada", "salida", "ajuste", name="tipo_movimiento_enum")


class Ingrediente(TimestampMixin, Base):
    """Ingrediente del catálogo global de Brasaland."""

    __tablename__ = "ingredientes"
    __table_args__ = (
        UniqueConstraint("codigo", name="uq_ingredientes_codigo"),
        CheckConstraint(
            "unidad IN ('kg','g','L','ml','unidad')", name="ck_ingredientes_unidad"
        ),
        CheckConstraint("costo_unitario >= 0", name="ck_ingredientes_costo_positivo"),
        {"comment": "Catálogo de ingredientes con costos y umbral mínimo"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    unidad: Mapped[str] = mapped_column(UnidadEnum, nullable=False, default="kg")
    stock_minimo: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    costo_unitario: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    moneda: Mapped[str] = mapped_column(String(3), nullable=False, default="COP")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True
    )

    # 1:N → un proveedor abastece muchos ingredientes
    proveedor: Mapped["Proveedor | None"] = relationship(
        back_populates="ingredientes", foreign_keys=[proveedor_id]
    )
    # 1:N → un ingrediente tiene stock en muchos locales
    inventarios: Mapped[list["InventarioLocal"]] = relationship(
        back_populates="ingrediente", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Ingrediente id={self.id} {self.codigo} {self.nombre}>"


class InventarioLocal(TimestampMixin, Base):
    """Stock de un ingrediente en un local (relación 1:N con Local)."""

    __tablename__ = "inventario_local"
    __table_args__ = (
        UniqueConstraint("local_id", "ingrediente_id", name="uq_inventario_local_ingrediente"),
        {"comment": "Stock actual por local e ingrediente"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    local_id: Mapped[int] = mapped_column(
        ForeignKey("locales.id", ondelete="CASCADE"), nullable=False
    )
    ingrediente_id: Mapped[int] = mapped_column(
        ForeignKey("ingredientes.id", ondelete="CASCADE"), nullable=False
    )
    cantidad_actual: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)
    cantidad_minima: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, default=0)

    local: Mapped["Local"] = relationship(back_populates="inventario")
    ingrediente: Mapped["Ingrediente"] = relationship(back_populates="inventarios")
    # 1:N → un registro de inventario tiene muchos movimientos (Kardex)
    movimientos: Mapped[list["MovimientoInventario"]] = relationship(
        back_populates="inventario", cascade="all, delete-orphan"
    )

    @property
    def necesita_reposicion(self) -> bool:
        """Regla de negocio: stock por debajo del mínimo → alerta."""
        return self.cantidad_actual <= self.cantidad_minima

    def __repr__(self) -> str:  # pragma: no cover
        return f"<InventarioLocal local={self.local_id} ing={self.ingrediente_id} cant={self.cantidad_actual}>"


class MovimientoInventario(Base):
    """Movimiento de inventario (entrada/salida/ajuste) — historial inmutable."""

    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('entrada','salida','ajuste')", name="ck_movimientos_tipo"
        ),
        CheckConstraint("cantidad > 0", name="ck_movimientos_cantidad_positiva"),
        Index("ix_movimientos_created_at", "created_at"),
        {"comment": "Kardex de movimientos: entradas, salidas y ajustes"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    inventario_local_id: Mapped[int] = mapped_column(
        ForeignKey("inventario_local.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(TipoMovimientoEnum, nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    inventario: Mapped["InventarioLocal"] = relationship(back_populates="movimientos")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<MovimientoInventario id={self.id} tipo={self.tipo} cant={self.cantidad}>"