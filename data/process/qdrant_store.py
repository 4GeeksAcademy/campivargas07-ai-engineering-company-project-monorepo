"""Qdrant storage operations; importing this module needs qdrant-client."""

from __future__ import annotations

import os
from typing import Any

COLLECTION_NAME = "brasaland_knowledge"


class QdrantConfigurationError(RuntimeError):
    pass


def create_client() -> Any:
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency
        raise RuntimeError("Install the API dependencies to use the knowledge vector store.") from exc
    url = os.getenv("QDRANT_URL", "http://localhost:6333").strip()
    if not url:
        raise QdrantConfigurationError("QDRANT_URL must not be empty.")
    return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY") or None)


def ensure_collection(client: Any, dimension: int) -> None:
    """Create a cosine collection, but never silently recreate a mismatch."""
    from qdrant_client.http import models

    if client.collection_exists(COLLECTION_NAME):
        info = client.get_collection(COLLECTION_NAME)
        configured_size = getattr(info.config.params.vectors, "size", None)
        if configured_size != dimension:
            raise ValueError(
                f"Qdrant collection {COLLECTION_NAME!r} dimension mismatch: "
                f"configured {configured_size}, requested {dimension}; explicit migration required."
            )
        distance = getattr(info.config.params.vectors, "distance", None)
        if distance != models.Distance.COSINE:
            raise ValueError(f"Qdrant collection {COLLECTION_NAME!r} must use cosine distance.")
        return
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )
