"""Unit tests for the backend client: hard method policy + service token.

These prove the network-level layer of the read-only inventory design: write
attempts are rejected BEFORE any HTTP request exists.
"""

from __future__ import annotations

import json
import time

import httpx
import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from brasaland_mcp.backend import (
    BackendAuthError,
    BackendTimeout,
    BackendUnavailable,
    BrasalandBackend,
    ServiceTokenAuthenticator,
    WriteNotAllowedError,
)


def _backend_with(handler, **kwargs) -> BrasalandBackend:
    return BrasalandBackend(
        "http://backend.test",
        transport=httpx.MockTransport(handler),
        token_provider=lambda: "token",
        **kwargs,
    )


def test_inventory_writes_rejected_before_network():
    recorded = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append((request.method, request.url.path))
        return httpx.Response(200, json=[])

    backend = _backend_with(handler)
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        for path in ("/inventory/products", "/inventory/products/abc", "/inventory/orders/inbound"):
            with pytest.raises(WriteNotAllowedError):
                backend.request(method, path)
    assert recorded == []  # nothing ever reached the transport


def test_generic_incident_patch_rejected_only_status_allowed():
    backend = _backend_with(lambda request: httpx.Response(200, json={}))
    with pytest.raises(WriteNotAllowedError):
        backend.request("PATCH", "/api/incidents/3f2a9c1b4d5e")
    # the lifecycle route itself is allowed
    response = backend.request("PATCH", "/api/incidents/3f2a9c1b4d5e/status", json_body={"status": "in_progress"})
    assert response.status_code == 200


def test_disallowed_routes_rejected():
    backend = _backend_with(lambda request: httpx.Response(200, json={}))
    with pytest.raises(WriteNotAllowedError):
        backend.request("GET", "/inventory/orders")  # not in the tool surface
    with pytest.raises(WriteNotAllowedError):
        backend.request("DELETE", "/api/incidents/3f2a9c1b4d5e")
    with pytest.raises(WriteNotAllowedError):
        backend.request("GET", "/auth/me")


def test_timeout_maps_to_backend_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom", request=request)

    backend = _backend_with(handler)
    with pytest.raises(BackendTimeout):
        backend.request("GET", "/api/incidents")


def test_connect_error_maps_to_backend_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    backend = _backend_with(handler)
    with pytest.raises(BackendUnavailable):
        backend.request("GET", "/api/incidents")


# ---------------------------------------------------------------------------
# ServiceTokenAuthenticator: real login flow, cache and 401 retry
# ---------------------------------------------------------------------------


def _service_jwt(ttl: int = 600) -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    now = int(time.time())
    return pyjwt.encode({"sub": "1", "exp": now + ttl, "iat": now}, pem, algorithm="RS256")


def test_service_login_and_cache():
    calls = {"login": 0, "api": 0}
    token = _service_jwt()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            calls["login"] += 1
            body = json.loads(request.content)
            assert body == {"email": "mcp-service@brasaland.test", "password": "secret"}
            return httpx.Response(200, json={"access_token": token})
        calls["api"] += 1
        assert request.headers["authorization"] == f"Bearer {token}"
        return httpx.Response(200, json=[])

    backend = BrasalandBackend(
        "http://backend.test",
        email="mcp-service@brasaland.test",
        password="secret",
        transport=httpx.MockTransport(handler),
    )
    backend.request("GET", "/api/incidents")
    backend.request("GET", "/api/incidents")
    assert calls == {"login": 1, "api": 2}  # token cached, single login


def test_service_token_relogin_on_401():
    state = {"logins": 0, "api_calls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            state["logins"] += 1
            return httpx.Response(200, json={"access_token": _service_jwt()})
        state["api_calls"] += 1
        if state["api_calls"] == 1:
            return httpx.Response(401, json={"detail": "expired"})
        return httpx.Response(200, json={"ok": True})

    backend = BrasalandBackend(
        "http://backend.test",
        email="mcp-service@brasaland.test",
        password="secret",
        transport=httpx.MockTransport(handler),
    )
    response = backend.request("GET", "/api/incidents")
    assert response.ok
    assert state == {"logins": 2, "api_calls": 2}  # single retry after re-login


def test_service_login_rejected_raises_auth_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/auth/login":
            return httpx.Response(401, json={"detail": "Incorrect email or password"})
        return httpx.Response(200, json=[])

    backend = BrasalandBackend(
        "http://backend.test",
        email="mcp-service@brasaland.test",
        password="bad",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(BackendAuthError):
        backend.request("GET", "/api/incidents")
