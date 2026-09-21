"""
cache.py — Brasaland · In-memory TTL cache with LRU eviction

Thread-safe TTL (time-to-live) cache used to speed up hot read endpoints
(supplier list / detail). Design goals:

- No external dependencies: stdlib only (``threading``, ``collections``,
  ``time``), so no new packages enter the lockfile.
- Deterministic keys: callers compose explicit keys (see ``build_key``).
- Injectable clock: ``clock`` defaults to ``time.monotonic`` (immune to wall
  clock changes); tests can inject a fake monotonic clock to expire entries
  instantly without ``sleep`` calls.
- Max size with LRU eviction: when full, the least-recently-used entry is
  evicted first (entries are also refreshed on read).
- Concurrency safe: every operation takes an ``RLock``.
- Observability: HIT/MISS/EVICT/EXPIRE counters plus per-operation ``logging``
  at DEBUG level; ``cache_stats`` returns a consistent snapshot.
- Defensive reads: cached values are deep-copied on the way out so callers
  cannot mutate shared state (Pydantic models are immutable via
  ``model_copy`` re-validation of deep-copied dicts; plain dicts/lists are
  copied structurally).

Never cache here (enforced by callers, documented in CACHING_REPORT.md):
``/auth/login`` (write), any mutation, 404 responses, ``/health``, private
responses (unless the caller includes an auth identity in the key).
"""

from __future__ import annotations

import copy
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Callable, Dict, Hashable, Optional, Tuple

logger = logging.getLogger("brasaland.cache")

Clock = Callable[[], float]


class TTLCache:
    """Thread-safe in-memory cache with per-entry TTL and LRU eviction."""

    def __init__(
        self,
        *,
        max_size: int = 128,
        default_ttl: float = 60.0,
        clock: Clock = time.monotonic,
        namespace: str = "default",
    ) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._clock = clock
        self._namespace = namespace
        # Ordered oldest-insertion -> newest; most recently used moved to end.
        self._store: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.RLock()
        # Stats
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expired = 0

    # ── Public API ──────────────────────────────────────────────

    def get(self, key: str) -> Tuple[bool, Any]:
        """Return (hit, value). Expired entries are treated as a MISS and purged."""
        now = self._clock()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                logger.debug("cache[%s] MISS key=%s", self._namespace, key)
                return False, None
            expire_at, value = entry
            if now >= expire_at:
                # Monotonic expiry: strictly expire once clock reaches expire_at.
                del self._store[key]
                self._expired += 1
                self._misses += 1
                logger.debug("cache[%s] EXPIRED key=%s", self._namespace, key)
                return False, None
            # Refresh recency (LRU behaviour).
            self._store.move_to_end(key)
            self._hits += 1
            logger.debug("cache[%s] HIT key=%s", self._namespace, key)
            return True, copy.deepcopy(value)

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Insert/update an entry with the given TTL (default: ``default_ttl``)."""
        effective_ttl = self._default_ttl if ttl is None else ttl
        if effective_ttl <= 0:
            # Zero/negative TTL means "do not cache".
            return
        now = self._clock()
        expire_at = now + effective_ttl
        with self._lock:
            self._store[key] = (expire_at, copy.deepcopy(value))
            self._store.move_to_end(key)
            self._evict_over_capacity(now)

    def delete(self, key: str) -> bool:
        """Remove a specific key. Returns True if it existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                logger.debug("cache[%s] DELETE key=%s", self._namespace, key)
                return True
            return False

    def invalidate_prefix(self, prefix: str) -> int:
        """Remove every key starting with ``prefix`` (namespace invalidation).

        Used to invalidate all list variants at once, e.g. every
        ``suppliers:list:v1:...`` key when a mutation lands.
        Returns the number of invalidated keys.
        """
        removed = 0
        with self._lock:
            for key in list(self._store.keys()):
                if key.startswith(prefix):
                    del self._store[key]
                    removed += 1
        if removed:
            logger.debug(
                "cache[%s] INVALIDATE prefix=%s removed=%d", self._namespace, prefix, removed
            )
        return removed

    def clear(self) -> None:
        """Drop all entries (used between tests to avoid cross-test pollution)."""
        with self._lock:
            self._store.clear()
            logger.debug("cache[%s] CLEAR", self._namespace)

    def cache_stats(self) -> Dict[str, Any]:
        """Return a consistent snapshot of counters and size."""
        with self._lock:
            return {
                "namespace": self._namespace,
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "expired": self._expired,
                "hit_rate": self._hit_rate_locked(),
            }

    # ── Helpers ─────────────────────────────────────────────────

    def _evict_over_capacity(self, now: float) -> None:
        """Purge expired entries first, then evict LRU entries if still over capacity."""
        expired_keys = [
            key for key, (expire_at, _) in self._store.items() if now >= expire_at
        ]
        for key in expired_keys:
            del self._store[key]
            self._expired += 1
        while len(self._store) > self._max_size:
            evicted_key, _ = self._store.popitem(last=False)  # oldest / least recent
            self._evictions += 1
            logger.debug("cache[%s] EVICT key=%s", self._namespace, evicted_key)

    def _hit_rate_locked(self) -> Optional[float]:
        total = self._hits + self._misses
        if total == 0:
            return None
        return round(self._hits / total, 4)


def build_key(*parts: Hashable) -> str:
    """Compose a deterministic, explicit cache key from ordered parts.

    Examples
    --------
    >>> build_key("suppliers", "list", "v1", "country=Colombia", "category=carne")
    'suppliers:list:v1:country=Colombia:category=carne'
    """
    normalized: list[str] = []
    for part in parts:
        if isinstance(part, bool):
            normalized.append(str(part).lower())
        else:
            normalized.append(str(part))
    return ":".join(normalized)


def normalize_filter(value: Optional[str]) -> str:
    """Normalize an optional filter query param for cache keys.

    Rules (deterministic, explicit):
    - ``None``  -> ``"*"`` (all)
    - otherwise: trimmed, case-preserved (values are exact enum strings in
      this API, e.g. ``Colombia`` / ``carne``), spaces collapsed.
    """
    if value is None:
        return "*"
    collapsed = " ".join(value.strip().split())
    return collapsed if collapsed else "*"
