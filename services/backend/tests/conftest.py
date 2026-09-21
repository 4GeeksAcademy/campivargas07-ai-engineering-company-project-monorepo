"""conftest.py — Fixtures de pytest para el backend Brasaland.

Estrategia:
- PostgreSQL: crea una BD efímera ``brasaland_test_db`` (CREATE DATABASE),
  aplica el esquema con ``Base.metadata.create_all`` y la elimina al terminar.
- MongoDB: usa la base ``brasaland_test`` (misma instancia Docker) y la suelta al final.
- La dependencia ``get_db`` se sobreescribe para apuntar a la BD de prueba.
- Un usuario admin se siembra para probar el flujo JWT completo.

Las BDs reales (brasaland_db / brasaland) nunca son tocadas por los tests.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import mongo
from app.common.security import hash_password
from app.common.base import Base
from app.config import settings
from app.database import get_db
from app.main import app

PG_TEST_DB = "brasaland_test_db"
MONGO_TEST_DB = "brasaland_test"

ADMIN_EMAIL = "admin@test.brasaland.com"
ADMIN_PASSWORD = "admin-test-123"


def _admin_url() -> str:
    """URL conectada a la BD 'postgres' (permite CREATE/DROP DATABASE)."""
    return settings.database_url.rsplit("/", 1)[0] + "/postgres"


def _test_url() -> str:
    return settings.database_url.rsplit("/", 1)[0] + "/" + PG_TEST_DB


@pytest.fixture(scope="session")
def _pg_engine():
    """Crea la BD de prueba con el esquema completo; la destruye al final."""
    admin_engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {PG_TEST_DB} WITH (FORCE)"))
        conn.execute(text(f"CREATE DATABASE {PG_TEST_DB}"))
    admin_engine.dispose()

    engine = create_engine(_test_url(), pool_pre_ping=True)
    # Importar app.main registró todos los modelos en Base.metadata
    Base.metadata.create_all(engine)
    yield engine

    engine.dispose()
    admin_engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        conn.execute(text(f"DROP DATABASE IF EXISTS {PG_TEST_DB} WITH (FORCE)"))
    admin_engine.dispose()


@pytest.fixture(scope="session")
def client(_pg_engine):
    """TestClient con BD de prueba: override de get_db + Mongo a brasaland_test."""
    settings.mongo_db = MONGO_TEST_DB  # connect_mongo() lee esta propiedad

    TestSession = sessionmaker(bind=_pg_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app = __import__("app.main", fromlist=["app"]).app
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

    # Limpieza de Mongo: dropear la BD de prueba
    cleanup = MongoClient(settings.mongo_url, serverSelectionTimeoutMS=5000)
    cleanup.drop_database(MONGO_TEST_DB)
    cleanup.close()


@pytest.fixture(scope="session")
def admin_token(client, _pg_engine) -> str:
    """Crea un usuario admin en la BD de prueba y devuelve su JWT."""
    from app.domains.auth.models import Usuario

    Session = sessionmaker(bind=_pg_engine)
    db = Session()
    if db.query(Usuario).filter_by(email=ADMIN_EMAIL).first() is None:
        db.add(
            Usuario(
                email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PASSWORD),
                rol="admin",
                activo=True,
            )
        )
        db.commit()
    db.close()

    r = client.post("/api/v1/auth/token", data={"username": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture()
def auth_headers(admin_token) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture()
def mongo_recetas():
    """Colección de recetas de prueba (para limpieza fina dentro de un test)."""
    return mongo.get_recetas_collection()