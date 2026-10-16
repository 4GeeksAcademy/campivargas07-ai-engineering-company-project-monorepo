"""Explicit configuration: no assumed student provider, model or credentials."""
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
COLLECTION = "brasaland_knowledge"
OWNER = "brasaland-rag-restart-v1"


class RagError(Exception):
    """Safe failure boundary for the API (details never returned to clients)."""


class ConfigurationError(RagError):
    pass


class ProviderError(RagError):
    pass


class StoreError(RagError):
    pass


@dataclass(frozen=True)
class Settings:
    embedding_url: str
    embedding_model: str
    embedding_key: str = field(repr=False)
    dimension: int
    encoding: str
    generation_url: str
    generation_model: str
    generation_key: str = field(repr=False)
    min_score: float
    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_key: str | None = field(default=None, repr=False)
    timeout: float = 30.0

    def __post_init__(self):
        if not self.embedding_model or not self.generation_model or self.embedding_model == self.generation_model:
            raise ConfigurationError("Configure modelos distintos para embeddings y generación")
        if not self.embedding_key or not self.generation_key:
            raise ConfigurationError("Faltan credenciales de modelos")
        if not 1 <= self.dimension <= 65536 or self.encoding not in {"float", "base64_int8"}:
            raise ConfigurationError("Dimensión o codificación no soportada")
        if not math.isfinite(self.min_score) or not -1 <= self.min_score <= 1:
            raise ConfigurationError("RAG_MIN_SCORE debe estar entre -1 y 1")
        if not math.isfinite(self.timeout) or not 0 < self.timeout <= 120:
            raise ConfigurationError("Timeout fuera de rango")
        for url in (self.embedding_url, self.generation_url, self.qdrant_url):
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ConfigurationError("URL inválida; use endpoints sin credenciales ni parámetros")
            if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "qdrant"}:
                raise ConfigurationError("El proveedor remoto requiere HTTPS")

    @property
    def vector_name(self) -> str:
        # A named vector binds even an empty collection to the embedding contract.
        contract = [self.embedding_url, self.embedding_model, self.dimension, self.encoding, "strip-v1"]
        return "embedding_" + sha256(json.dumps(contract).encode()).hexdigest()[:24]

    def public(self) -> dict:
        return {"embedding_model": self.embedding_model, "generation_model": self.generation_model,
                "dimension": self.dimension, "encoding": self.encoding, "distance": "Cosine",
                "min_score": self.min_score, "vector_name": self.vector_name}


def settings() -> Settings:
    def required(name):
        value = os.getenv(name, "").strip()
        if not value:
            raise ConfigurationError(f"Falta {name}")
        return value
    # This is an operator acknowledgement of the contract, not evidence of access.
    if required("RAG_HTTP_CONTRACT") != "embeddings-chat-v1":
        raise ConfigurationError("Contrato no soportado; confirme el contrato del proveedor")
    try:
        return Settings(
            embedding_url=required("RAG_EMBEDDING_URL"), embedding_model=required("RAG_EMBEDDING_MODEL"),
            embedding_key=required("RAG_EMBEDDING_API_KEY"), dimension=int(required("RAG_EMBEDDING_DIMENSION")),
            encoding=required("RAG_EMBEDDING_ENCODING"), generation_url=required("RAG_GENERATION_URL"),
            generation_model=required("RAG_GENERATION_MODEL"), generation_key=required("RAG_GENERATION_API_KEY"),
            min_score=float(required("RAG_MIN_SCORE")), qdrant_url=os.getenv("QDRANT_URL", "http://127.0.0.1:6333"),
            qdrant_key=os.getenv("QDRANT_API_KEY") or None,
            timeout=float(os.getenv("RAG_TIMEOUT_SECONDS", "30")),
        )
    except ValueError as exc:
        raise ConfigurationError("Configuración numérica RAG inválida") from exc
