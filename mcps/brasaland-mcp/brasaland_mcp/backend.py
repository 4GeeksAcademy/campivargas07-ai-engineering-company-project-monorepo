"""HTTP client for the MCP -> Brasaland API boundary (boundary 2).

Design:
- The MCP server authenticates with a *dedicated service account* through the
  real `POST /auth/login` (JSON {email, password} -> {access_token}). The token
  is cached in memory and refreshed before expiry; on a 401 the client logs in
  once more and retries a single time.
- The user's OAuth token from boundary 1 is NEVER forwarded to the backend
  (different issuer/audience/secret) and the backend SECRET_KEY is never copied
  here. User authorization is enforced by MCP scopes before any call happens.
- A hard method policy makes the inventory surface read-only *by construction*:
  any non-GET attempt against /inventory/* raises before a single byte hits the
  network. This is the server-side rejection backing the read-only tools.
- Timeouts are explicit; redirects are never followed; request bodies, tokens
  and error details are never logged.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
import jwt


class BackendTimeout(Exception):
    """The Brasaland API exceeded the configured timeout."""


class BackendUnavailable(Exception):
    """The Brasaland API is unreachable or returned a server error."""


class BackendAuthError(Exception):
    """The MCP service account could not authenticate against the backend."""


class WriteNotAllowedError(Exception):
    """A write operation was attempted against a read-only backend surface."""

    def __init__(self, method: str, path: str):
        super().__init__(f"{method} {path} is not allowed: read-only surface")
        self.method = method
        self.path = path


# Hard allowlist of (method, path-prefix) the MCP may issue. Anything else is
# rejected locally, before any HTTP call. Inventory is GET-only by design.
_ALLOWED_CALLS: tuple[tuple[str, str], ...] = (
    ("GET", "/api/incidents"),
    ("POST", "/api/incidents"),
    ("PATCH", "/api/incidents/"),  # only /{id}/status, refined in _check_policy
    ("GET", "/inventory/products"),
    ("POST", "/auth/login"),
)

_TOKEN_REFRESH_MARGIN_SECONDS = 30.0
_DEFAULT_TOKEN_TTL_SECONDS = 240.0


@dataclass(frozen=True)
class BackendResponse:
    status_code: int
    body: Any
    ok: bool


def _check_policy(method: str, path: str) -> None:
    """Reject anything outside the allowlist before it reaches the network."""
    if method == "PATCH" and path.startswith("/api/incidents/"):
        if not path.endswith("/status"):
            raise WriteNotAllowedError(method, path)
        return
    for allowed_method, allowed_prefix in _ALLOWED_CALLS:
        if method == allowed_method and path.startswith(allowed_prefix):
            return
    raise WriteNotAllowedError(method, path)


class ServiceTokenAuthenticator:
    """Logs in the MCP service account and caches the backend JWT in memory."""

    def __init__(self, client: httpx.Client, email: str, password: str):
        self._client = client
        self._email = email
        self._password = password
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at = 0.0

    def _login(self) -> str:
        try:
            response = self._client.post(
                "/auth/login",
                json={"email": self._email, "password": self._password},
                headers={"Accept": "application/json"},
            )
        except httpx.TimeoutException as exc:
            raise BackendTimeout("Backend login timed out") from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailable("Backend login failed") from exc
        if response.status_code in {401, 403}:
            raise BackendAuthError("MCP service account rejected by the backend")
        if response.status_code >= 500:
            raise BackendUnavailable("Backend login unavailable")
        try:
            token = response.json()["access_token"]
        except (ValueError, KeyError, TypeError) as exc:
            raise BackendUnavailable("Backend login response malformed") from exc
        if not isinstance(token, str) or not token:
            raise BackendUnavailable("Backend login response malformed")
        return token

    @staticmethod
    def _token_ttl(token: str) -> float:
        """Read `exp` without verifying the signature (token came from our own
        backend over the configured URL; used only for refresh bookkeeping)."""
        try:
            payload = jwt.decode(token, options={"verify_signature": False})
            exp = payload.get("exp")
            if isinstance(exp, (int, float)):
                return max(float(exp) - time.time(), 0.0)
        except jwt.PyJWTError:
            pass
        return _DEFAULT_TOKEN_TTL_SECONDS

    def get(self) -> str:
        with self._lock:
            if self._token is not None and time.monotonic() < self._expires_at:
                return self._token
            token = self._login()
            self._token = token
            self._expires_at = time.monotonic() + max(
                self._token_ttl(token) - _TOKEN_REFRESH_MARGIN_SECONDS, 1.0
            )
            return token

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0


class _CallableTokenProvider:
    """Adapter so plain callables satisfy the `.get()`/`.invalidate()` shape."""

    def __init__(self, provider):
        self._provider = provider

    def get(self) -> str:
        return self._provider()

    def invalidate(self) -> None:  # nothing to refresh for static providers
        pass


class BrasalandBackend:
    """Typed, policy-checked HTTP client towards the real Brasaland API."""

    def __init__(
        self,
        base_url: str,
        *,
        email: Optional[str] = None,
        password: Optional[str] = None,
        timeout_seconds: float = 5.0,
        transport: Optional[httpx.BaseTransport] = None,
        token_provider: Optional[Any] = None,
    ):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
        )
        if token_provider is not None:
            self._authenticator = (
                token_provider
                if hasattr(token_provider, "get")
                else _CallableTokenProvider(token_provider)
            )
        elif email and password:
            self._authenticator = ServiceTokenAuthenticator(self._client, email, password)
        else:
            raise ValueError("BrasalandBackend requires credentials or a token_provider")

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json_body: Optional[dict[str, Any]] = None,
    ) -> BackendResponse:
        """Issue a policy-checked, authenticated call. Retries once on 401."""
        _check_policy(method, path)
        response = self._send(method, path, params=params, json_body=json_body)
        if response.status_code == 401 and isinstance(
            self._authenticator, ServiceTokenAuthenticator
        ):
            self._authenticator.invalidate()
            response = self._send(method, path, params=params, json_body=json_body)
        body: Any = None
        if response.status_code != 204:
            try:
                body = response.json()
            except ValueError:
                body = None
        return BackendResponse(
            status_code=response.status_code,
            body=body,
            ok=200 <= response.status_code < 300,
        )

    def _send(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]],
        json_body: Optional[dict[str, Any]],
    ) -> httpx.Response:
        token = self._authenticator.get()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        try:
            return self._client.request(
                method, path, params=params, json=json_body, headers=headers
            )
        except httpx.TimeoutException as exc:
            raise BackendTimeout(f"{method} {path} timed out") from exc
        except httpx.HTTPError as exc:
            raise BackendUnavailable(f"{method} {path} failed") from exc

    def close(self) -> None:
        self._client.close()
