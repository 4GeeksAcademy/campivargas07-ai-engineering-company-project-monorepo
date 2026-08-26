"""
conftest.py — Global fixtures for Brasaland API tests

Provides isolated in-memory/tempfile TinyDB persistence and reusable test clients.
Ensures services/data/suppliers.json is NEVER touched.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from tinydb import TinyDB

import app.database as database
import app.domains.auth.dependencies as auth_deps
import app.domains.auth.router as auth_router
import app.domains.auth.service as auth_service
import app.domains.procurement.suppliers.service as suppliers_service
import app.domains.profiles.service as profiles_service
import app.domains.users.service as users_service
from app.main import app


@pytest.fixture(autouse=True)
def test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Generator[TinyDB, None, None]:
    """
    Creates a temporary, isolated TinyDB instance for every test.
    Patches all domain modules to use the temporary tables.
    """
    db_file = tmp_path / "isolated_test_db.json"
    isolated_db = TinyDB(db_file)

    users_tbl = isolated_db.table("users")
    profiles_tbl = isolated_db.table("profiles")
    suppliers_tbl = isolated_db.table("suppliers")

    # Patch database module
    monkeypatch.setattr(database, "db", isolated_db)
    monkeypatch.setattr(database, "users_table", users_tbl)
    monkeypatch.setattr(database, "profiles_table", profiles_tbl)
    monkeypatch.setattr(database, "suppliers_table", suppliers_tbl)

    # Patch modules that directly imported tables
    monkeypatch.setattr(auth_router, "users_table", users_tbl)
    monkeypatch.setattr(auth_router, "profiles_table", profiles_tbl)
    monkeypatch.setattr(auth_deps, "users_table", users_tbl)
    monkeypatch.setattr(users_service, "users_table", users_tbl)
    monkeypatch.setattr(users_service, "profiles_table", profiles_tbl)
    monkeypatch.setattr(profiles_service, "profiles_table", profiles_tbl)
    monkeypatch.setattr(suppliers_service, "suppliers_table", suppliers_tbl)

    yield isolated_db

    isolated_db.close()


@pytest.fixture
def client(test_db: TinyDB) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with isolated DB."""
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def create_test_user(test_db: TinyDB):
    """Helper fixture to insert test users into the isolated database."""
    def _create(
        email: str = "usuario.prueba@brasaland.com",
        password: str = "password123",
        role: str = "user",
        is_active: bool = True,
        name: str | None = "Usuario Prueba",
        phone: str | None = "+57 300 123 4567",
        address: str | None = "Calle 100 # 15-20, Bogotá",
    ) -> dict:
        users_tbl = test_db.table("users")
        profiles_tbl = test_db.table("profiles")

        hashed = auth_service.hash_password(password)
        user_doc = {
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
    """Helper fixture to obtain Authorization Bearer headers for a default user."""
    user = create_test_user()
    token = auth_service.create_access_token(
        data={"sub": str(user.doc_id), "role": user["role"]}
    )
    return {"Authorization": f"Bearer {token}"}

