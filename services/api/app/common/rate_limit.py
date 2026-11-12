"""Shared in-memory rate limiting helpers for Brasaland API and WebSocket flows.

The limiter is intentionally process-local. It protects model-invoking and other
sensitive endpoints without adding Redis. Callers must treat the limits as
per-process guarantees; see docs/security/nist-security-practices.md.
"""

from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from typing import Tuple

_RATE_LIMITS: dict[str, deque[float]] = defaultdict(deque)
_LOCK = threading.Lock()


def _disabled() -> bool:
    return os.environ.get("BRASALAND_ENV", "").strip().lower() in {"test"}


def check_rate_limit(key: str, limit: int, window_seconds: float = 60.0) -> Tuple[bool, float]:
    """Return (allowed, retry_after_seconds). Thread-safe, process-local."""
    if _disabled():
        return True, 0.0
    if limit <= 0:
        return False, window_seconds
    now = time.monotonic()
    with _LOCK:
        bucket = _RATE_LIMITS[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = window_seconds - (now - bucket[0])
            return False, max(retry, 0.0)
        bucket.append(now)
        return True, 0.0


def reset_rate_limits() -> None:
    with _LOCK:
        _RATE_LIMITS.clear()