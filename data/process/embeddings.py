"""Explicit Perplexity INT8 and opt-in compatible float HTTP embeddings."""

from __future__ import annotations

import base64
import binascii
import math
import os
from typing import Any

import httpx

from data.process.provider_http import api_base_url, positive_timeout, post_json


class EmbeddingConfigurationError(RuntimeError):
    """An embedding contract has not been explicitly configured."""


def embedding_configuration() -> dict[str, Any]:
    """Non-secret vector-space identity, shared by documents and queries."""
    provider = os.getenv("EMBEDDING_PROVIDER", "").strip()
    model = os.getenv("EMBEDDING_MODEL", "").strip()
    encoding = os.getenv("EMBEDDING_ENCODING_FORMAT", "").strip()
    try:
        dimensions = int(os.getenv("EMBEDDING_DIMENSIONS", ""))
    except ValueError as exc:
        raise EmbeddingConfigurationError("Set EMBEDDING_DIMENSIONS to the approved positive dimension.") from exc
    if provider not in {"perplexity", "openai_compatible"} or not model or dimensions <= 0:
        raise EmbeddingConfigurationError("Set EMBEDDING_PROVIDER, EMBEDDING_MODEL and EMBEDDING_DIMENSIONS.")
    endpoint = api_base_url("EMBEDDING_API_BASE_URL")
    if provider == "perplexity":
        maximum = {"pplx-embed-v1-0.6b": 1024, "pplx-embed-v1-4b": 2560}.get(model)
        if endpoint != "https://api.perplexity.ai/v1" or maximum is None:
            raise EmbeddingConfigurationError("Perplexity standard embeddings require /v1 and a documented standard model.")
        if encoding != "base64_int8" or not 128 <= dimensions <= maximum:
            raise EmbeddingConfigurationError("Perplexity requires base64_int8 and a supported dimension (128..model maximum).")
    elif encoding != "float":
        raise EmbeddingConfigurationError("The compatible adapter requires an explicitly confirmed float contract.")
    return {
        "provider": provider, "endpoint": endpoint, "model": model,
        "dimensions": dimensions, "encoding_format": encoding, "preprocessing": "identity-v1",
    }


def validate_embedding(value: Any, *, expected_dimension: int | None = None) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError("Embedding provider returned an empty or invalid vector.")
    if expected_dimension is not None and (type(expected_dimension) is not int or expected_dimension <= 0):
        raise ValueError("Expected embedding dimension must be a positive integer.")
    vector: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError("Embedding vector contains a non-numeric value.")
        try:
            number = float(item)
        except OverflowError as exc:
            raise ValueError("Embedding vector contains an invalid numeric value.") from exc
        if not math.isfinite(number):
            raise ValueError("Embedding vector contains a non-finite value.")
        vector.append(number)
    if expected_dimension is not None and len(vector) != expected_dimension:
        raise ValueError(f"Embedding dimension mismatch: expected {expected_dimension}, received {len(vector)}.")
    if not any(vector):
        raise ValueError("Embedding provider returned a zero vector.")
    return vector


def decode_int8(value: Any, *, dimensions: int) -> list[float]:
    """Decode strict base64 bytes as SIGNED int8, with no uint8 interpretation."""
    if not isinstance(value, str) or not value:
        raise ValueError("Expected a base64_int8 embedding string.")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Embedding provider returned invalid base64_int8.") from exc
    return validate_embedding(
        [float(byte if byte < 128 else byte - 256) for byte in raw], expected_dimension=dimensions,
    )


def embed(text: str, *, expected_dimension: int | None = None, client: httpx.Client | None = None) -> list[float]:
    """Embed unchanged text under the same explicit contract on both paths."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding input must be non-empty text.")
    config = embedding_configuration()
    dimensions = config["dimensions"]
    if expected_dimension is not None and expected_dimension != dimensions:
        raise ValueError("Embedding dimension mismatch with the configured vector space.")
    api_key = os.getenv("EMBEDDING_API_KEY", "").strip() or None
    if config["provider"] == "perplexity" and not api_key:
        raise EmbeddingConfigurationError("Set EMBEDDING_API_KEY locally for Perplexity.")
    payload = {"model": config["model"], "input": text}
    if config["provider"] == "perplexity":
        payload.update(dimensions=dimensions, encoding_format="base64_int8")
    # A compatible proxy receives only its minimal confirmed float payload;
    # Perplexity-specific quantization parameters are never imposed on it.
    body = post_json(
        f"{config['endpoint']}/embeddings", payload, api_key=api_key,
        timeout=positive_timeout("EMBEDDING_TIMEOUT_SECONDS", "30"), client=client, provider="Embedding",
    )
    if body.get("model", config["model"]) != config["model"]:
        raise ValueError("Embedding provider returned a different model.")
    if body.get("encoding_format", config["encoding_format"]) != config["encoding_format"]:
        raise ValueError("Embedding provider returned a different encoding format.")
    try:
        items = body["data"]
        if not isinstance(items, list) or len(items) != 1 or items[0].get("index", 0) != 0:
            raise ValueError("Expected exactly one embedding at index zero.")
        value = items[0]["embedding"]
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise ValueError("Embedding provider returned an invalid response.") from exc
    if config["encoding_format"] == "base64_int8":
        return decode_int8(value, dimensions=dimensions)
    return validate_embedding(value, expected_dimension=dimensions)
