"""
cache.py — In-Memory TTL Cache for Telemetry Reports

Features:
- Configurable TTL (default 60 seconds).
- Monotonic clock (time.monotonic) to evaluate expiration accurately without wall-clock skew.
- Cache key by (start_date_iso, end_date_iso) or (None, None) for parameterless queries.
- Retains both resolved window and metrics payload during the TTL.
- Completely separate from pure analysis functions and database operations.
"""

from __future__ import annotations

import time
from typing import Any, Optional

DEFAULT_REPORT_TTL_SECONDS = 60.0


class CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, expires_at: float):
        self.value = value
        self.expires_at = expires_at

    def is_expired(self, now: float) -> bool:
        return now >= self.expires_at


class TelemetryReportCache:
    """Simple in-memory thread-safe cache with TTL and monotonic clock."""

    def __init__(self, default_ttl: float = DEFAULT_REPORT_TTL_SECONDS):
        self._default_ttl = default_ttl
        self._entries: dict[tuple[Optional[str], Optional[str]], CacheEntry] = {}

    def _make_key(
        self,
        start_date_iso: Optional[str],
        end_date_iso: Optional[str],
    ) -> tuple[Optional[str], Optional[str]]:
        return (start_date_iso, end_date_iso)

    def get(
        self,
        start_date_iso: Optional[str],
        end_date_iso: Optional[str],
    ) -> Optional[Any]:
        """Returns cached report if present and not expired; otherwise None."""
        key = self._make_key(start_date_iso, end_date_iso)
        entry = self._entries.get(key)
        if entry is None:
            return None

        now = time.monotonic()
        if entry.is_expired(now):
            self._entries.pop(key, None)
            return None

        return entry.value

    def set(
        self,
        start_date_iso: Optional[str],
        end_date_iso: Optional[str],
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Stores report in cache with TTL based on monotonic clock."""
        key = self._make_key(start_date_iso, end_date_iso)
        duration = ttl if ttl is not None else self._default_ttl
        expires_at = time.monotonic() + duration
        self._entries[key] = CacheEntry(value=value, expires_at=expires_at)

    def clear(self) -> None:
        """Flushes all cached entries."""
        self._entries.clear()


# Module-level singleton cache for reports
report_cache = TelemetryReportCache()
