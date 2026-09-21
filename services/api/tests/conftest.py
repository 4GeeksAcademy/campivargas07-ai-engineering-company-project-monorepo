"""
conftest.py — Global fixtures for Brasaland API tests

Provides:
- Isolated temporary TinyDB database for every test.
- Patches all domain modules using TinyDB tables.
- In-memory SQLite database with foreign keys enabled for fast unit testing.
- Dependency overrides for get_db.
- Reusable test user and authentication fixtures.
- Optional PostgreSQL test engine fixture via TEST_DATABASE_URL.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel
from tinydb import TinyDB

import app.database as database
import app.domains.auth.dependencies as auth_deps
import app.domains.auth.router as auth_router
import app.domains.auth.service as auth_service
import app.domains.procurement.suppliers.service as suppliers_service
import app.domains.profiles.service as profiles_service
import app.domains.users.service as users_service
from app.database import get_db, init_db
from app.main import app


# --- TinyDB Isolation ---
@pytest.fixture(autouse=True)
def test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TinyDB, None, None]:
    """Creates a temporary isolated TinyDB database for every test."""
    # A developer's root .env may point at a real PostgreSQL instance. Tests use
    # the SQLite fixture below and must never connect to that external database.
    monkeypatch.delenv("DATABASE_URL", raising=False)

    db_file = tmp_path / "isolated_test_db.json"
    isolated_db = TinyDB(db_file)

    users_tbl = isolated_db.table("users")
    profiles_tbl = isolated_db.table("profiles")
    password_resets_tbl = isolated_db.table("password_resets")
    suppliers_tbl = isolated_db.table("suppliers")

    # Patch database module
    monkeypatch.setattr(database, "db", isolated_db)
    monkeypatch.setattr(database, "users_table", users_tbl)
    monkeypatch.setattr(database, "profiles_table", profiles_tbl)
    monkeypatch.setattr(database, "password_resets_table", password_resets_tbl)
    monkeypatch.setattr(database, "suppliers_table", suppliers_tbl)

    # Patch domain modules that directly imported tables
    monkeypatch.setattr(auth_router, "users_table", users_tbl)
    monkeypatch.setattr(auth_router, "profiles_table", profiles_tbl)
    monkeypatch.setattr(auth_router, "password_resets_table", password_resets_tbl)
    monkeypatch.setattr(auth_deps, "users_table", users_tbl)
    monkeypatch.setattr(users_service, "users_table", users_tbl)
    monkeypatch.setattr(users_service, "profiles_table", profiles_tbl)
    monkeypatch.setattr(profiles_service, "profiles_table", profiles_tbl)
    monkeypatch.setattr(suppliers_service, "suppliers_table", suppliers_tbl)

    yield isolated_db
    isolated_db.close()


# --- Fast SQLite Database for Unit Tests ---
@pytest.fixture
def sqlite_engine():
    """In-memory SQLite engine with PRAGMA foreign_keys=ON and StaticPool."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    init_db(bind_engine=engine)
    yield engine
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(sqlite_engine) -> Generator[Session, None, None]:
    """Session for the isolated SQLite engine."""
    with Session(sqlite_engine) as session:
        yield session


# --- Reusable Test User & Auth Headers ---
@pytest.fixture
def create_test_user(test_db: TinyDB):
    """Helper fixture to insert an authenticated user into the isolated TinyDB."""
    def _create(
        email: str = "usuario.prueba@brasaland.com",
        password: str = "password123",
        role: str = "user",
        is_active: bool = True,
        name: str | None = "Usuario Prueba",
        phone: str | None = "+57 300 123 4567",
        address: str | None = "Calle 100 # 15-20, Bogotá",
        user_uuid: str | None = None,
    ) -> dict:
        users_tbl = test_db.table("users")
        profiles_tbl = test_db.table("profiles")

        hashed = auth_service.hash_password(password)
        assigned_uuid = user_uuid or str(uuid.uuid4())
        user_doc = {
            "uuid": assigned_uuid,
            "email": email,
            "hashed_password": hashed,
            "role": role,
            "is_active": is_active,
            "created_at": "2026-08-01T12:00:00+00:00",
        }
        doc_id = users_tbl.insert(user_doc)
        users_tbl.update({"doc_id": doc_id}, doc_ids=[doc_id])

        if any(v is not None for v in (name, phone, address)):
            profile_doc = {
                "user_id": str(doc_id),
                "name": name,
                "phone": phone,
                "address": address,
            }
            prof_id = profiles_tbl.insert(profile_doc)
            profiles_tbl.update({"doc_id": prof_id}, doc_ids=[prof_id])

        return users_tbl.get(doc_id=doc_id)

    return _create


@pytest.fixture
def auth_headers(create_test_user):
    """Provides valid Bearer authorization headers."""
    user = create_test_user()
    token = auth_service.create_access_token(
        data={"sub": str(user.doc_id), "role": user["role"]}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client(sqlite_engine) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to use the isolated SQLite DB."""
    def _override_get_db():
        with Session(sqlite_engine) as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
