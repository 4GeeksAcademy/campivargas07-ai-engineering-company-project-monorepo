"""Environment-driven configuration for the Brasaland MCP server.

No credential or provider value has an invented default: issuer, resource id,
backend URL and the MCP service-account credentials are mandatory and come
exclusively from the environment (.env is Git-ignored; see .env.example).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlsplit


class ConfigError(RuntimeError):
    """Raised when mandatory configuration is missing or malformed."""


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing mandatory environment variable: {name}")
    return value


def _absolute_http_url(name: str, value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(f"{name} must be an absolute http(s) URL, got: {value!r}")
    return value.rstrip("/")


def _positive_float(name: str, raw: str, default: float) -> float:
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be a number, got: {raw!r}") from exc
    if value <= 0:
        raise ConfigError(f"{name} must be > 0, got: {value!r}")
    return value


@dataclass(frozen=True)
class Settings:
    """Immutable runtime settings resolved once at startup."""

    # --- Boundary 1: OAuth resource server (client -> MCP) ---
    resource_id: str
    """Public identifier of this MCP server (RFC 8707); also the expected `aud`.
    In Codespaces this MUST be the public forwarded HTTPS URL of the MCP port."""

    auth_issuer: str
    """OIDC/OAuth 2.1 issuer URL of the external authorization server."""

    auth_server_type: str
    """`oidc` (OpenID Connect discovery) or `oauth` (RFC 8414)."""

    # --- Boundary 2: MCP -> Brasaland API (service account) ---
    backend_url: str
    """Base URL of the Brasaland FastAPI backend (internal; never exposed)."""

    backend_email: str
    backend_password: str
    """Dedicated MCP service account on the Brasaland backend. Environment-only."""

    backend_timeout_seconds: float = 5.0

    # --- HTTP server ---
    host: str = "127.0.0.1"
    port: int = 9100
    log_level: str = "INFO"


def load_settings() -> Settings:
    """Resolve and validate settings from the environment (fail fast)."""
    resource_id = _absolute_http_url(
        "MCP_RESOURCE_ID", _require("MCP_RESOURCE_ID")
    )
    auth_issuer = _absolute_http_url("MCP_AUTH_ISSUER", _require("MCP_AUTH_ISSUER"))
    auth_type = os.getenv("MCP_AUTH_SERVER_TYPE", "oidc").strip().lower()
    if auth_type not in {"oidc", "oauth"}:
        raise ConfigError(f"MCP_AUTH_SERVER_TYPE must be 'oidc' or 'oauth', got: {auth_type!r}")

    backend_url = _absolute_http_url("BRASALAND_API_URL", _require("BRASALAND_API_URL"))

    port_raw = os.getenv("MCP_PORT", "9100").strip()
    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ConfigError(f"MCP_PORT must be an integer, got: {port_raw!r}") from exc
    if not 1 <= port <= 65535:
        raise ConfigError(f"MCP_PORT out of range: {port}")

    return Settings(
        resource_id=resource_id,
        auth_issuer=auth_issuer,
        auth_server_type=auth_type,
        backend_url=backend_url,
        backend_email=_require("MCP_BACKEND_SERVICE_EMAIL"),
        backend_password=_require("MCP_BACKEND_SERVICE_PASSWORD"),
        backend_timeout_seconds=_positive_float(
            "MCP_BACKEND_TIMEOUT_SECONDS",
            os.getenv("MCP_BACKEND_TIMEOUT_SECONDS", "").strip(),
            5.0,
        ),
        host=os.getenv("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1",
        port=port,
        log_level=os.getenv("MCP_LOG_LEVEL", "INFO").strip().upper() or "INFO",
    )
