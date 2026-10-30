"""Unit tests for env-driven configuration (fail-fast, no invented defaults)."""

from __future__ import annotations

import pytest

from brasaland_mcp.config import ConfigError, load_settings


def _set_env(monkeypatch, **overrides):
    base = {
        "MCP_RESOURCE_ID": "https://cs-9100.app.github.dev/mcp",
        "MCP_AUTH_ISSUER": "https://issuer.example/",
        "BRASALAND_API_URL": "http://127.0.0.1:8000",
        "MCP_BACKEND_SERVICE_EMAIL": "mcp-service@brasaland.test",
        "MCP_BACKEND_SERVICE_PASSWORD": "secret",
    }
    base.update(overrides)
    for key, value in base.items():
        monkeypatch.setenv(key, value)


def test_load_settings_defaults(monkeypatch):
    _set_env(monkeypatch)
    settings = load_settings()
    assert settings.resource_id == "https://cs-9100.app.github.dev/mcp"
    assert settings.auth_issuer == "https://issuer.example"  # trailing slash normalized
    assert settings.auth_server_type == "oidc"
    assert settings.backend_url == "http://127.0.0.1:8000"
    assert settings.backend_timeout_seconds == 5.0
    assert settings.host == "127.0.0.1"
    assert settings.port == 9100


def test_missing_mandatory_variable_fails(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.delenv("MCP_AUTH_ISSUER")
    with pytest.raises(ConfigError, match="MCP_AUTH_ISSUER"):
        load_settings()


def test_missing_service_credentials_fail(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.delenv("MCP_BACKEND_SERVICE_PASSWORD")
    with pytest.raises(ConfigError, match="MCP_BACKEND_SERVICE_PASSWORD"):
        load_settings()


def test_relative_urls_rejected(monkeypatch):
    _set_env(monkeypatch, BRASALAND_API_URL="backend:8000")
    with pytest.raises(ConfigError, match="absolute http"):
        load_settings()


def test_invalid_port_rejected(monkeypatch):
    _set_env(monkeypatch, MCP_PORT="70000")
    with pytest.raises(ConfigError, match="MCP_PORT"):
        load_settings()


def test_invalid_auth_type_rejected(monkeypatch):
    _set_env(monkeypatch, MCP_AUTH_SERVER_TYPE="magic")
    with pytest.raises(ConfigError, match="MCP_AUTH_SERVER_TYPE"):
        load_settings()
