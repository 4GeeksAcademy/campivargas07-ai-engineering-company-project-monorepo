"""database.py — Brasaland · Sesión PostgreSQL (SQLAlchemy)

Motor síncrono con psycopg2 y SessionFactory compartido.
Cada request obtiene su propia sesión vía la dependencia get_db().
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # revive conexiones caídas (importante con Docker)
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: entrega una sesión y siempre la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()