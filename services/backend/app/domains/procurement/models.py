"""models.py — Brasaland · Modelos de Proveedores y vínculo N:M con Locales

- ``Proveedor``       → proveedor de ingredientes (puede servir a varios locales)
- ``LocalProveedor``  → tabla intermedia de la relación muchos-a-muchos
                        locales ↔ proveedores, con atributos propios
                        (precio acordado, lead time, es principal).
"""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.ingredients.models import Ingrediente
    from app.domains.locations.models import Local

PaisEnum = Enum("CO", "US", name="pais_enum")


class Proveedor(TimestampMixin, Base):
    """Proveedor de ingredientes para los locales."""

    __tablename__ = "proveedores"
    __table_args__ = (
        UniqueConstraint("nombre", name="uq_proveedores_nombre"),
        CheckConstraint("pais IN ('CO','US')", name="ck_proveedores_pais"),
        {"comment": "Proveedores de ingredientes (N:M con locales)"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    contacto: Mapped[str] = mapped_column(String(120), nullable=True)
    telefono: Mapped[str] = mapped_column(String(30), nullable=True)
    pais: Mapped[str] = mapped_column(PaisEnum, nullable=False, server_default="CO")
    dias_entrega: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 1:N → un proveedor abastece muchos ingredientes
    ingredientes: Mapped[list["Ingrediente"]] = relationship(back_populates="proveedor")
    # N:M → un proveedor sirve a muchos locales (tabla intermedia)
    locales: Mapped[list["LocalProveedor"]] = relationship(
        back_populates="proveedor", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Proveedor id={self.id} {self.nombre}>"


class LocalProveedor(Base):
    """Tabla intermedia N:M: Local ↔ Proveedor con atributos de la relación."""

    __tablename__ = "locales_proveedores"
    __table_args__ = (
        UniqueConstraint("local_id", "proveedor_id", name="uq_local_proveedor"),
        {"comment": "Relación N:M locales-proveedores con condiciones comerciales"},
    )

    local_id: Mapped[int] = mapped_column(
        ForeignKey("locales.id", ondelete="CASCADE"), primary_key=True
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="CASCADE"), primary_key=True
    )
    es_principal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    precio_acordado: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=True)
    lead_time_dias: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    local: Mapped["Local"] = relationship(back_populates="proveedores")
    proveedor: Mapped["Proveedor"] = relationship(back_populates="locales")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LocalProveedor local={self.local_id} prov={self.proveedor_id}>"