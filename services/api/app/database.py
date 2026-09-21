"""
database.py — Brasaland · Dual database initialization (TinyDB + SQLModel/PostgreSQL)

Centralized database access for all domains:
- TinyDB for existing users, profiles, and suppliers.
- SQLModel (PostgreSQL/Supabase) for ingredients and inventory orders.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Generator

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine
from tinydb import TinyDB

# Load environment variables if .env exists locally
load_dotenv()

# --- TinyDB Configuration ---
_default_path = Path(__file__).resolve().parent.parent.parent / "data" / "suppliers.json"
_db_path = Path(os.environ.get("SUPPLIERS_DB_PATH", str(_default_path)))
_db_path.parent.mkdir(parents=True, exist_ok=True)

db = TinyDB(_db_path)

suppliers_table = db.table("suppliers")
users_table = db.table("users")
profiles_table = db.table("profiles")


def backfill_users_uuid() -> int:
    """
    Idempotent backfill: ensures every existing user in TinyDB has a stable 'uuid'.
    Uses uuid5 based on doc_id if absent. Returns count of backfilled users.
    """
    updated = 0
    for user_doc in users_table.all():
        if "uuid" not in user_doc:
            stable_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"brasaland-user-{user_doc.doc_id}"))
            users_table.update({"uuid": stable_uuid}, doc_ids=[user_doc.doc_id])
            updated += 1
    return updated


# --- SQLModel / PostgreSQL Engine Configuration ---
_engine = None


def get_db_engine():
    """Returns the SQLModel engine configured exclusively via DATABASE_URL."""
    global _engine
    if _engine is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not configured. "
                "Please configure DATABASE_URL in your environment."
            )
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def get_db() -> Generator[Session, None, None]:
    """FastAPI request-scoped database session dependency."""
    engine = get_db_engine()
    with Session(engine) as session:
        yield session


def init_db(bind_engine=None) -> None:
    """
    Initializes SQLModel tables.
    Explicitly imports all domain models before create_all to ensure registration.
    """
    # Import domain models before table creation
    from app.domains.operations.inventory.models import (  # noqa: F401
        Ingredient,
        IngredientEntry,
        IngredientExit,
    )

    engine = bind_engine or get_db_engine()
    SQLModel.metadata.create_all(engine)
