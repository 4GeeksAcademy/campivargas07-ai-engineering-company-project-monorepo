"""Shared test harness: local mock OIDC provider + mock Brasaland backend.

Everything here exercises the REAL verification path: tokens are real RS256
JWTs signed with a local key whose public JWKS the mcpauth verifier fetches
over real HTTP. The backend is an httpx.MockTransport that records every
request so tests can assert which routes were (and were never) reached.
"""

from __future__ import annotations

import base64
import contextlib
import json
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Optional

import jwt
import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from mcpauth.config import AuthServerConfig, AuthServerType, AuthorizationServerMetadata

from brasaland_mcp.app import build_app
from brasaland_mcp.auth import create_mcp_auth
from brasaland_mcp.backend import BrasalandBackend
from brasaland_mcp.config import Settings

TEST_ISSUER = "https://brasaland-test-issuer"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ---------------------------------------------------------------------------
# Mock OIDC provider (real JWKS over real HTTP)
# ---------------------------------------------------------------------------


class OidcProvider:
    """Issues RS256 tokens and serves the public key as JWKS."""

    def __init__(self) -> None:
        self._key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._pem = self._key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        numbers = self._key.public_key().public_numbers()
        self._jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "brasaland-test",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64uint(numbers.n),
                    "e": _b64uint(numbers.e),
                }
            ]
        }
        provider = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                body = json.dumps(provider._jwks).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self._httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        self.jwks_uri = f"http://127.0.0.1:{self._httpd.server_address[1]}/jwks"

    def mint(
        self,
        scopes: list[str],
        *,
        sub: str = "test-user-1",
        client_id: str = "test-client",
        aud: str,
        iss: str = TEST_ISSUER,
        exp_offset: int = 3600,
    ) -> str:
        now = int(time.time())
        payload = {
            "iss": iss,
            "sub": sub,
            "aud": aud,
            "client_id": client_id,
            "scope": " ".join(scopes),
            "iat": now,
            "exp": now + exp_offset,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(payload, self._pem, algorithm="RS256", headers={"kid": "brasaland-test"})

    def auth_server_config(self) -> AuthServerConfig:
        return AuthServerConfig(
            metadata=AuthorizationServerMetadata(
                issuer=TEST_ISSUER,
                authorization_endpoint=f"{TEST_ISSUER}/authorize",
                token_endpoint=f"{TEST_ISSUER}/token",
                jwks_uri=self.jwks_uri,
                response_types_supported=["code"],
                scopes_supported=["incidents:read", "incidents:write", "inventory:read"],
            ),
            type=AuthServerType.OIDC,
        )

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()


def _b64uint(value: int) -> str:
    length = (value.bit_length() + 7) // 8
    return base64.urlsafe_b64encode(value.to_bytes(length, "big")).rstrip(b"=").decode()


@pytest.fixture(scope="session")
def oidc_provider():
    provider = OidcProvider()
    yield provider
    provider.stop()


# ---------------------------------------------------------------------------
# Mock Brasaland backend (records every request)
# ---------------------------------------------------------------------------

SAMPLE_INCIDENT = {
    "id": "3f2a9c1b4d5e",
    "title": "Parrilla con temperatura irregular",
    "description": "La parrilla principal no alcanza la temperatura objetivo.",
    "category": "EQUIPMENT",
    "status": "open",
    "branch": "MED-01",
    "reported_at": "2026-10-01T12:00:00Z",
    "updated_at": "2026-10-01T12:00:00Z",
    "origin": "api",
    "external_ref": None,
}

SAMPLE_PRODUCT = {
    "id": "2b6d7f9a-1c2e-4a3b-9d8f-0a1b2c3d4e5f",
    "sku": "ING-001",
    "name": "Costilla BBQ",
    "category": "carne",
    "unit_of_measure": "kg",
    "minimum_stock": "20.0",
    "perishable": True,
    "created_at": "2026-09-01T00:00:00Z",
    "local_id": "MED-001",
    "current_stock": "25.0",
}


@dataclass
class RecordedRequest:
    method: str
    path: str
    params: dict[str, Any]
    body: Any
    has_auth: bool


@dataclass
class MockBrasaland:
    """Canned-response backend that records every HTTP request it receives."""

    requests: list[RecordedRequest] = field(default_factory=list)
    responses: dict[tuple[str, str], tuple[int, Any]] = field(default_factory=dict)
    default_status: int = 404
    default_body: Any = field(
        default_factory=lambda: {"code": 404, "message": "Not found", "field": None, "request_id": "test"}
    )
    raise_timeout: bool = False
    raise_connect_error: bool = False

    def set_response(self, method: str, path: str, status: int, body: Any) -> None:
        self.responses[(method.upper(), path)] = (status, body)

    def write_requests(self) -> list[RecordedRequest]:
        return [r for r in self.requests if r.method.upper() not in {"GET", "HEAD", "OPTIONS"}]

    def handler(self):
        import httpx

        def _handle(request: httpx.Request) -> httpx.Response:
            if self.raise_timeout:
                raise httpx.ReadTimeout("simulated timeout", request=request)
            if self.raise_connect_error:
                raise httpx.ConnectError("simulated connect error", request=request)
            body: Any = None
            if request.content:
                with contextlib.suppress(ValueError):
                    body = json.loads(request.content)
            self.requests.append(
                RecordedRequest(
                    method=request.method,
                    path=request.url.path,
                    params=dict(request.url.params),
                    body=body,
                    has_auth=request.headers.get("authorization", "").startswith("Bearer "),
                )
            )
            key = (request.method, request.url.path)
            if key in self.responses:
                status, payload = self.responses[key]
            else:
                status, payload = self.default_status, self.default_body
            return httpx.Response(status, json=payload)

        return _handle


@pytest.fixture()
def mock_brasaland() -> MockBrasaland:
    return MockBrasaland()


@pytest.fixture()
def backend(mock_brasaland) -> BrasalandBackend:
    import httpx

    client_backend = BrasalandBackend(
        "http://backend.test",
        timeout_seconds=5.0,
        transport=httpx.MockTransport(mock_brasaland.handler()),
        token_provider=lambda: "service-jwt-token",
    )
    yield client_backend
    client_backend.close()


# ---------------------------------------------------------------------------
# MCP server harness (real uvicorn + real MCP streamable-http protocol)
# ---------------------------------------------------------------------------


@dataclass
class McpServerHarness:
    base_url: str
    resource_id: str
    settings: Settings

    @property
    def mcp_url(self) -> str:
        return f"{self.base_url}/mcp"

    @property
    def metadata_url(self) -> str:
        return f"{self.base_url}/.well-known/oauth-protected-resource/mcp"


@pytest.fixture()
def mcp_server(oidc_provider, mock_brasaland) -> McpServerHarness:
    port = _free_port()
    resource_id = f"http://127.0.0.1:{port}/mcp"
    settings = Settings(
        resource_id=resource_id,
        auth_issuer=TEST_ISSUER,
        auth_server_type="oidc",
        backend_url="http://backend.test",
        backend_email="mcp-service@brasaland.test",
        backend_password="not-used-in-tests",
        backend_timeout_seconds=5.0,
        host="127.0.0.1",
        port=port,
    )
    import httpx

    test_backend = BrasalandBackend(
        settings.backend_url,
        timeout_seconds=settings.backend_timeout_seconds,
        transport=httpx.MockTransport(mock_brasaland.handler()),
        token_provider=lambda: "service-jwt-token",
    )
    mcp_auth = create_mcp_auth(settings, auth_server_config=oidc_provider.auth_server_config())
    app = build_app(settings, mcp_auth=mcp_auth, backend=test_backend)

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started:
        if time.monotonic() > deadline:
            raise RuntimeError("test MCP server failed to start")
        time.sleep(0.02)

    yield McpServerHarness(base_url=f"http://127.0.0.1:{port}", resource_id=resource_id, settings=settings)

    server.should_exit = True
    thread.join(timeout=5)
    test_backend.close()


# ---------------------------------------------------------------------------
# MCP client helpers (real protocol over streamable-http)
# ---------------------------------------------------------------------------


@dataclass
class ToolCallOutcome:
    """Normalized result of a tools/call attempt."""

    error: Optional[str] = None  # protocol-level error text, if any
    is_error: bool = False
    payload: Optional[dict[str, Any]] = None  # parsed structured envelope


def _parse_tool_result(result) -> ToolCallOutcome:
    if result.isError:
        texts = [getattr(block, "text", "") for block in result.content]
        return ToolCallOutcome(is_error=True, error=" ".join(texts))
    for block in result.content:
        text = getattr(block, "text", None)
        if text:
            with contextlib.suppress(ValueError):
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return ToolCallOutcome(payload=parsed)
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return ToolCallOutcome(payload=structured)
    return ToolCallOutcome(is_error=True, error="unparseable tool result")


def run_mcp_session(
    mcp_url: str,
    token: Optional[str],
    action: str,
    tool_name: str = "",
    arguments: Optional[dict[str, Any]] = None,
):
    """Execute one MCP action (initialize/list_tools/call_tool) and normalize.

    Returns:
      - for call_tool: ToolCallOutcome
      - for list_tools: list of tools
      - transport-level failures are returned as ToolCallOutcome(error=...)
    """
    import anyio
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async def _run():
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        async with streamablehttp_client(mcp_url, headers=headers) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                if action == "list_tools":
                    listed = await session.list_tools()
                    return listed.tools
                result = await session.call_tool(tool_name, arguments or {})
                return _parse_tool_result(result)

    async def _guarded():
        try:
            return await _run()
        except BaseException as exc:
            # anyio surfaces transport failures as ExceptionGroups; normalize
            # both shapes into a single error field.
            if isinstance(exc, BaseExceptionGroup):
                first = exc.exceptions[0]
                return ToolCallOutcome(error=f"{type(first).__name__}: {first}")
            return ToolCallOutcome(error=f"{type(exc).__name__}: {exc}")

    return anyio.run(_guarded)


def call_tool(harness: McpServerHarness, token: Optional[str], name: str, arguments: dict[str, Any]) -> ToolCallOutcome:
    outcome = run_mcp_session(harness.mcp_url, token, "call_tool", name, arguments)
    assert isinstance(outcome, ToolCallOutcome)
    return outcome


def list_tools(harness: McpServerHarness, token: Optional[str]):
    return run_mcp_session(harness.mcp_url, token, "list_tools")


# ---------------------------------------------------------------------------
# Token fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def token_full(oidc_provider, mcp_server) -> str:
    return oidc_provider.mint(
        ["incidents:read", "incidents:write", "inventory:read"], aud=mcp_server.resource_id
    )


@pytest.fixture()
def token_readonly(oidc_provider, mcp_server) -> str:
    """Client that only consults: incidents read + inventory read."""
    return oidc_provider.mint(
        ["incidents:read", "inventory:read"], aud=mcp_server.resource_id
    )
