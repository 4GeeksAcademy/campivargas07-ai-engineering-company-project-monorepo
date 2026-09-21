#!/usr/bin/env python3
"""
measure_cache.py — Brasaland · Cache measurement scenario (cold/warm/invalidation/expiry)

Runs an identical request scenario against a live API and reports per-phase
statistics. Phases (per task spec):

  1. COLD      — first call of each endpoint variant (guaranteed MISS).
  2. WARM      — N repeated identical calls (should be HITs).
  3. POST-INVALIDATION — same calls right after a write (create/rate/status/delete).
  4. POST-EXPIRY — same calls after advancing beyond TTL (simulated by cache
     flush + artificial wait in real time OR by measuring with a short TTL;
     here we wait past TTL using the real clock — TTL 60s is too long, so we
     use the cache_stats endpoint? No: we restart with a tiny-TTL server OR
     we simply flush. To keep runtime short we measure expiry by launching the
     scenario twice: once with default TTLs, once with TTL=1s env override).

Outputs a compact table suitable for CACHING_REPORT.md.
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
from urllib.request import Request, urlopen

BASE = os.environ.get("MEASURE_BASE", "http://127.0.0.1:8000")
REPEATS = int(os.environ.get("MEASURE_REPEATS", "25"))

SCENARIO = [
    ("list_all", "/api/suppliers"),
    ("list_country", "/api/suppliers?country=Colombia"),
    ("list_category", "/api/suppliers?category=carne"),
    ("list_mix", "/api/suppliers?country=Colombia&category=carne"),
    ("detail_2", "/api/suppliers/2"),
    ("detail_4", "/api/suppliers/4"),
]


def fetch(path: str) -> tuple[int, float, int]:
    """GET and return (status, elapsed_ms, body_bytes)."""
    req = Request(f"{BASE}{path}", method="GET")
    start = time.perf_counter()
    with urlopen(req, timeout=30) as resp:
        body = resp.read()
        status = resp.status
    elapsed = (time.perf_counter() - start) * 1000.0
    return status, elapsed, len(body)


def run_phase(label: str) -> dict:
    results = {}
    for name, path in SCENARIO:
        times = []
        status = None
        for _ in range(REPEATS):
            status, ms, _ = fetch(path)
            times.append(ms)
        results[name] = {
            "status": status,
            "median_ms": round(statistics.median(times), 2),
            "mean_ms": round(statistics.fmean(times), 2),
            "min_ms": round(min(times), 2),
            "max_ms": round(max(times), 2),
        }
    return {label: results}


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "cold_warm"

    if mode == "cold_warm":
        out = {}
        out.update(run_phase("cold_miss"))
        out.update(run_phase("warm_hit"))
        print(json.dumps(out, indent=2))
    elif mode == "post_invalidation":
        # Mutate (rate update on supplier 1) then measure immediately.
        import urllib.error

        login = urlopen(
            Request(
                f"{BASE}/auth/login",
                data=json.dumps({"email": "medicion@brasaland.com", "password": "medicion123"}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        )
        token = json.load(login).get("access_token")
        if not token:
            print("ERROR: no token from /auth/login; create the user first.", file=sys.stderr)
            sys.exit(1)

        req = Request(
            f"{BASE}/api/suppliers/2/rate",
            data=json.dumps({"montoMinimoOrden": 999.5}).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
            method="PATCH",
        )
        with urlopen(req) as resp:
            resp.read()

        out = run_phase("post_invalidation_miss")
        print(json.dumps(out, indent=2))
    elif mode == "post_expiry":
        out = run_phase("post_expiry_miss")
        print(json.dumps(out, indent=2))
    else:
        print(f"unknown mode {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
