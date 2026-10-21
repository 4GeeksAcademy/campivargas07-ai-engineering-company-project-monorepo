"""HTTP contract adapters, enabled only after the operator confirms compatibility."""
import base64
import binascii
import math
import struct

import httpx

from data.process.config import ProviderError, Settings, settings


def post_json(url: str, key: str, payload: dict, timeout: float, client=None) -> dict:
    try:
        if client is None:
            with httpx.Client(timeout=timeout, follow_redirects=False) as session:
                return post_json(url, key, payload, timeout, session)
        response = client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Expected object")
        return result
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("El proveedor no devolvió una respuesta válida") from exc


def validate_vector(vector, dimension: int) -> list[float]:
    if not isinstance(vector, list) or len(vector) != dimension:
        raise ProviderError("Dimensión de embedding inesperada")
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in vector):
        raise ProviderError("Embedding no numérico o no finito")
    if not any(vector):
        raise ProviderError("Embedding nulo")
    return [float(x) for x in vector]


def embed(text: str, *, config: Settings | None = None, client=None) -> list[float]:
    cfg = config or settings()
    if not isinstance(text, str) or not text.strip():
        raise ValueError("El texto no puede estar vacío")
    result = post_json(cfg.embedding_url, cfg.embedding_key, {
        "model": cfg.embedding_model, "input": [text.strip()],
        "dimensions": cfg.dimension, "encoding_format": cfg.encoding,
    }, cfg.timeout, client)
    try:
        if result["model"] != cfg.embedding_model or len(result["data"]) != 1:
            raise ValueError("Modelo o cantidad inesperados")
        item = result["data"][0]
        if item.get("index", 0) != 0:
            raise ValueError("Índice inesperado")
        vector = item["embedding"]
        if cfg.encoding == "base64_int8":
            if not isinstance(vector, str):
                raise ValueError("Se esperaba base64_int8")
            raw = base64.b64decode(vector, validate=True)
            vector = list(struct.unpack(f"{len(raw)}b", raw))
        return validate_vector(vector, cfg.dimension)
    except (KeyError, TypeError, ValueError, IndexError, binascii.Error, struct.error) as exc:
        raise ProviderError("Contrato de embeddings inválido") from exc
