#!/usr/bin/env python3
"""Measure supplier cache MISS and HIT requests against a live API.

Cold phases record exactly one request per variant immediately after a
namespace invalidation. Warm phases report only repeated requests made after a
separate cache-population request. Expiry mode warms keys and waits beyond the
longest TTL before taking one MISS sample per variant.
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


def summarize(status: int, times: list[float]) -> dict:
    return {
        "status": status,
        "samples": len(times),
        "median_ms": round(statistics.median(times), 2),
        "mean_ms": round(statistics.fmean(times), 2),
        "min_ms": round(min(times), 2),
        "max_ms": round(max(times), 2),
    }


def run_cold_phase(label: str) -> dict:
    """Measure exactly one request per variant; caller invalidates first."""
    results = {}
    for name, path in SCENARIO:
        status, ms, _ = fetch(path)
        results[name] = summarize(status, [ms])
    return {label: results}


def run_warm_phase(label: str) -> dict:
    results = {}
    for name, path in SCENARIO:
        # Populate the key independently from the measured HIT samples.
        status, _, _ = fetch(path)
        times = []
        for _ in range(REPEATS):
            status, ms, _ = fetch(path)
            times.append(ms)
        results[name] = summarize(status, times)
    return {label: results}


def invalidate_with_rate_update() -> None:
    """Perform an authenticated write that invalidates all supplier keys."""
    login = urlopen(
        Request(
            f"{BASE}/auth/login",
            data=json.dumps({"email": "medicion@brasaland.com", "password": "medicion123"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        ),
        timeout=30,
    )
    token = json.load(login).get("access_token")
    if not token:
        raise RuntimeError("no token from /auth/login; create the measurement user first")

    req = Request(
        f"{BASE}/api/suppliers/2/rate",
        data=json.dumps({"montoMinimoOrden": 999.5}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="PATCH",
    )
    with urlopen(req, timeout=30) as resp:
        resp.read()


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "cold_warm"

    if mode == "cold_warm":
        invalidate_with_rate_update()
        out = {}
        out.update(run_cold_phase("cold_miss"))
        out.update(run_warm_phase("warm_hit"))
        print(json.dumps(out, indent=2))
    elif mode == "post_invalidation":
        invalidate_with_rate_update()
        out = run_cold_phase("post_invalidation_miss")
        out.update(run_warm_phase("post_invalidation_warm_hit"))
        print(json.dumps(out, indent=2))
    elif mode == "post_expiry":
        for _, path in SCENARIO:
            fetch(path)
        wait_seconds = float(os.environ.get("MEASURE_EXPIRY_WAIT", "121"))
        print(f"Waiting {wait_seconds:g}s for supplier cache TTL expiry...", file=sys.stderr)
        time.sleep(wait_seconds)
        out = run_cold_phase("post_expiry_miss")
        out.update(run_warm_phase("post_expiry_warm_hit"))
        print(json.dumps(out, indent=2))
    else:
        print(f"unknown mode {mode}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
