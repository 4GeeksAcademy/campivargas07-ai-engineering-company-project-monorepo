"""base.py — Brasaland · Base declarativa compartida

Todos los modelos SQLAlchemy de los dominios heredan de ``Base``.
Alembic usa ``Base.metadata`` (via env.py) para autogenerar migraciones.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa de SQLAlchemy 2.0 para todos los modelos."""
    pass


class TimestampMixin:
    """Mixin reutilizable: created_at / updated_at gestionados por PostgreSQL."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )