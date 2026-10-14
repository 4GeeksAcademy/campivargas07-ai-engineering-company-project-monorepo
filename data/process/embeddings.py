"""Small HTTP adapter for explicitly configured OpenAI-compatible embeddings."""

from __future__ import annotations

import math
import os
from typing import Any

import httpx


class EmbeddingConfigurationError(RuntimeError):
    """Raised when an approved embedding endpoint is not configured."""


def _settings() -> tuple[str, str, str | None, float]:
    base_url = os.getenv("EMBEDDING_API_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    api_key = os.getenv("EMBEDDING_API_KEY")
    timeout = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "30"))
    if not base_url or not model:
        raise EmbeddingConfigurationError(
            "Embedding provider is not configured: set EMBEDDING_API_BASE_URL and EMBEDDING_MODEL."
        )
    return base_url, model, api_key, timeout


def validate_embedding(value: Any, *, expected_dimension: int | None = None) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("Embedding provider returned an empty or invalid vector.")
    vector: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("Embedding vector contains a non-numeric value.")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError("Embedding vector contains a non-finite value.")
        vector.append(number)
    if expected_dimension is not None and len(vector) != expected_dimension:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dimension}, received {len(vector)}."
        )
    return vector


def embed(text: str, *, expected_dimension: int | None = None, client: httpx.Client | None = None) -> list[float]:
    """Return one validated vector using configured /embeddings endpoint."""
    base_url, model, api_key, timeout = _settings()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    payload = {"model": model, "input": text}
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.post(f"{base_url}/embeddings", json=payload, headers=headers)
        response.raise_for_status()
        body = response.json()
    except httpx.HTTPError as exc:
        raise RuntimeError("Embedding provider request failed.") from exc
    finally:
        if owns_client:
            http.close()
    try:
        vector = body["data"][0]["embedding"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Embedding provider returned an invalid response.") from exc
    return validate_embedding(vector, expected_dimension=expected_dimension)
