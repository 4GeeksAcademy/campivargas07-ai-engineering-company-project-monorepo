"""models.py — Brasaland · Modelo Local (PostgreSQL)

Un Local es un restaurante de la cadena. Brasaland opera 14 locales
en Colombia (COP) y Florida, USA (USD).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.domains.inventory.models import InventarioLocal
    from app.domains.procurement.models import LocalProveedor

PaisEnum = Enum("CO", "US", name="pais_enum")
MonedaEnum = Enum("COP", "USD", name="moneda_enum")


class Local(TimestampMixin, Base):
    """Local (restaurante) de la cadena Brasaland."""

    __tablename__ = "locales"
    __table_args__ = (
        CheckConstraint("pais IN ('CO','US')", name="ck_locales_pais"),
        CheckConstraint("moneda IN ('COP','USD')", name="ck_locales_moneda"),
        {"comment": "Restaurantes de la cadena: Colombia y Florida"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    ciudad: Mapped[str] = mapped_column(String(80), nullable=False)
    pais: Mapped[str] = mapped_column(PaisEnum, nullable=False, server_default="CO")
    moneda: Mapped[str] = mapped_column(MonedaEnum, nullable=False, server_default="COP")
    direccion: Mapped[str] = mapped_column(String(200), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 1:N → un local tiene muchos registros de inventario
    inventario: Mapped[list["InventarioLocal"]] = relationship(
        back_populates="local", cascade="all, delete-orphan"
    )
    # N:M → un local trabaja con muchos proveedores (tabla intermedia)
    proveedores: Mapped[list["LocalProveedor"]] = relationship(
        back_populates="local", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Local id={self.id} {self.nombre} ({self.ciudad}/{self.pais})>"