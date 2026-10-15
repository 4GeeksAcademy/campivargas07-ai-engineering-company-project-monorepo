"""Qdrant storage operations; importing this module needs qdrant-client."""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlsplit

COLLECTION_NAME = "brasaland_knowledge"
EMBEDDING_CONFIGURATION_KEY = "embedding_configuration"


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


def validate_configuration(configuration: Any) -> dict[str, Any]:
    """Keep the non-secret embedding identity shared by indexing and retrieval."""
    keys = {"provider", "endpoint", "model", "dimensions", "encoding_format", "preprocessing"}
    if not isinstance(configuration, dict) or set(configuration) != keys:
        raise ValueError("A complete non-secret embedding configuration is required.")
    dimension = configuration["dimensions"]
    if isinstance(dimension, bool) or not isinstance(dimension, int) or dimension < 1:
        raise ValueError("Embedding configuration dimensions must be a positive integer.")
    if any(
        not isinstance(configuration[key], str) or not configuration[key].strip()
        for key in keys - {"dimensions"}
    ):
        raise ValueError("Embedding configuration identifiers must be nonempty strings.")
    endpoint = urlsplit(configuration["endpoint"])
    if (
        endpoint.scheme not in {"http", "https"}
        or not endpoint.hostname
        or endpoint.username is not None
        or endpoint.password is not None
        or endpoint.query
        or endpoint.fragment
    ):
        raise ValueError("Embedding configuration endpoint must exclude authentication, query and fragment.")
    return dict(configuration)


def ensure_collection(
    client: Any,
    dimension: int,
    *,
    embedding_config: dict[str, Any],
    create: bool = True,
) -> None:
    """Validate every stored embedding identity before a mutation or query.

    Existing points without configuration cannot safely be assumed compatible.
    An explicit migration is required; this function never deletes or recreates
    a collection. Retrieval sets ``create=False`` to remain read-only.
    """
    from qdrant_client.http import models

    configuration = validate_configuration(embedding_config)
    if dimension != configuration["dimensions"]:
        raise ValueError("Embedding dimension mismatch with its configured identity.")
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
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                offset=offset,
                with_payload=[EMBEDDING_CONFIGURATION_KEY],
                with_vectors=False,
            )
            for point in points:
                stored = (point.payload or {}).get(EMBEDDING_CONFIGURATION_KEY)
                try:
                    compatible = validate_configuration(stored) == configuration
                except ValueError:
                    compatible = False
                if not compatible:
                    raise ValueError(
                        f"Qdrant collection {COLLECTION_NAME!r} embedding configuration mismatch "
                        "or missing metadata; explicit migration required."
                    )
            if offset is None:
                break
        return
    if not create:
        raise ValueError(f"Qdrant collection {COLLECTION_NAME!r} has not been indexed.")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=models.VectorParams(size=dimension, distance=models.Distance.COSINE),
    )
