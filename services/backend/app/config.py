"""config.py — Brasaland · Configuración central del backend

Lee las variables de entorno con pydantic-settings.
El .env se carga desde la RAÍZ del monorepo (sube 3 niveles desde services/backend/app/)
para que docker compose y la app compartan las mismas credenciales.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env de la raíz del monorepo (services/backend/app/../../.. = raíz)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    """Configuración tipada de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- PostgreSQL ---
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "brasaland_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # --- MongoDB ---
    mongo_user: str = "brasaland"
    mongo_password: str = "brasaland"
    mongo_db: str = "brasaland"
    mongo_host: str = "localhost"
    mongo_port: int = 27017

    # --- Seguridad ---
    secret_key: str = "cambia-esta-clave-en-produccion"
    access_token_expire_minutes: int = 30

    @property
    def database_url(self) -> str:
        """URL de conexión síncrona para SQLAlchemy + psycopg2."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def mongo_url(self) -> str:
        """URL de conexión a MongoDB con autenticación."""
        return (
            f"mongodb://{self.mongo_user}:{self.mongo_password}"
            f"@{self.mongo_host}:{self.mongo_port}/{self.mongo_db}?authSource=admin"
        )


@lru_cache
def get_settings() -> Settings:
    """Instancia única de configuración (cacheada)."""
    return Settings()


settings = get_settings()