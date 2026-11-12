"""Tests for model-endpoint rate limiting."""

from fastapi.testclient import TestClient


def test_agent_query_rate_limit_returns_429(client: TestClient, auth_headers: dict, monkeypatch):
    import os
    from app.common.rate_limit import reset_rate_limits

    monkeypatch.setenv("BRASALAND_ENV", "development")
    monkeypatch.setenv("RATE_LIMIT_AGENT_PER_MINUTE", "2")
    reset_rate_limits()

    # First two requests pass the limiter (may be 401/503 but not 429).
    for _ in range(2):
        response = client.post("/agent/query", json={"question": "hola"}, headers=auth_headers)
        assert response.status_code != 429

    third = client.post("/agent/query", json={"question": "hola"}, headers=auth_headers)
    assert third.status_code == 429

    # Restore test mode.
    monkeypatch.setenv("BRASALAND_ENV", "test")
    reset_rate_limits()