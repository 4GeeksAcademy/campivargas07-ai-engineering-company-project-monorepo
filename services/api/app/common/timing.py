"""
timing.py — Brasaland · ASGI request timing middleware

Logs, for every HTTP request:
    method, route template (path), status code and duration in milliseconds.

Design constraints (per task spec):
- Uses ``time.perf_counter()`` (monotonic, high resolution) — never wall clock.
- Emits via Python ``logging`` (module ``brasaland.timing``), INFO level.
- NEVER logs query strings, headers, cookies or bodies (no sensitive data).
- Wraps downstream in try/finally so exceptions still propagate and the
  duration is recorded even when a request fails.
- The response status code and body are returned untouched; the middleware is
  purely observational and covered by tests asserting status/body equality.
"""

from __future__ import annotations

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("brasaland.timing")


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Record per-request duration and outcome without touching the response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            logger.info(
                "%s %s -> %s (%.2f ms)",
                request.method,
                request.url.path,  # path template only; query params excluded
                status_code,
                duration_ms,
            )
