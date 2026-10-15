"""Shared HTTP boundary for the two small knowledge model adapters."""

from __future__ import annotations

import math
import os
from typing import Any
from urllib.parse import urlsplit

import httpx


def api_base_url(variable: str) -> str:
    value = os.getenv(variable, "").strip().rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError(f"{variable} must be an HTTP(S) base URL without credentials, query or fragment.")
    return value


def positive_timeout(variable: str, default: str) -> float:
    value = float(os.getenv(variable, default))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{variable} must be finite and positive.")
    return value


def post_json(
    url: str, payload: dict[str, Any], *, api_key: str | None,
    timeout: float, client: httpx.Client | None, provider: str,
) -> dict[str, Any]:
    owns_client = client is None
    http = client or httpx.Client(timeout=timeout)
    try:
        response = http.post(
            url, json=payload, headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
            timeout=timeout,
        )
        response.raise_for_status()
        try:
            body = response.json()
        except ValueError as exc:
            raise ValueError(f"{provider} provider returned invalid JSON.") from exc
        if not isinstance(body, dict):
            raise ValueError(f"{provider} provider returned an invalid response object.")
        return body
    except httpx.HTTPError as exc:
        # Never copy response bodies, URLs or headers into public errors.
        raise RuntimeError(f"{provider} provider request failed.") from exc
    finally:
        if owns_client:
            http.close()
