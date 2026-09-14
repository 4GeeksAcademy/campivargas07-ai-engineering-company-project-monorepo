"""models.py — Brasaland · Modelo Usuario (para JWT del hito)

Tabla mínima de usuarios para proteger los endpoints de escritura
(Actividad Extra del hito: autenticación con JWT).
Separado de services/api (que usa TinyDB) a propósito: este backend
es la persistencia real en PostgreSQL.
"""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.common.base import Base, TimestampMixin


class Usuario(TimestampMixin, Base):
    """Usuario del backoffice con rol para autorización básica."""

    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("email", name="uq_usuarios_email"),
        CheckConstraint("rol IN ('admin','operador','consulta')", name="ck_usuarios_rol"),
        {"comment": "Usuarios del backoffice para JWT"},
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(120), nullable=True)
    rol: Mapped[str] = mapped_column(String(20), nullable=False, default="consulta")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Usuario id={self.id} {self.email} rol={self.rol}>"