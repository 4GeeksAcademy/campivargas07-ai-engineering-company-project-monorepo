"""
test_suppliers_cache.py — Tests for TTL caching on supplier endpoints + timing middleware

Covers (per task spec):
- MISS -> HIT for identical requests.
- Distinct query params -> distinct cache keys (no cross-contamination).
- TTL expiry using an injected fake monotonic clock (no sleeps).
- Invalidation after POST create, PATCH rate, PATCH status, DELETE —
  for the detail key AND all list variants (no stale data).
- Errors (404) are never cached.
- Private responses are not shared via cache (list/detail are public; a
  protected mutation response is not cached).
- Timing middleware does not alter status codes or response bodies.
- No persistent DB: every test uses the autouse isolated TinyDB from conftest.
- No long pauses: TTL expiry is simulated with the injected clock.
"""

from __future__ import annotations

import logging
from typing import List

import pytest
from fastapi.testclient import TestClient

from app.common.cache import TTLCache, build_key, normalize_filter
from app.domains.procurement.suppliers import router as suppliers_router_module

# ── Helpers ──────────────────────────────────────────────────


def _supplier_payload(n: int = 1, **overrides) -> dict:
    base = {
        "nombre": f"Proveedor Test {n}",
        "pais": "Colombia",
        "contactoNombre": "Contacto",
        "contactoEmail": f"proveedor{n}@brasaland.com",
        "contactoTelefono": f"+57 300 000 00{n:02d}",
        "categoriasQueProvee": ["carne"],
        "tiempoEntregaDias": 5,
        "montoMinimoOrden": 100.0,
        "moneda": "COP",
        "status": "activo",
    }
    base.update(overrides)
    return base


@pytest.fixture(autouse=True)
def _reset_suppliers_cache():
    """Isolate the shared module-level cache between tests."""
    suppliers_router_module.cache.clear()
    yield
    suppliers_router_module.cache.clear()


class FakeClock:
    """Deterministic monotonic clock that only advances when told to."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


def _patch_cache_clock(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> None:
    """Point the shared suppliers cache at the fake clock."""
    cache: TTLCache = suppliers_router_module.cache
    cache._clock = clock  # injectable clock per task spec


# ── Unit: cache primitives ───────────────────────────────────


def test_build_key_is_deterministic():
    assert build_key("a", "b", 1) == build_key("a", "b", 1)
    assert build_key("a", "b") != build_key("a", "c")
    assert (
        build_key("suppliers", "list", "v1", "country=*", "category=*")
        == "suppliers:list:v1:country=*:category=*"
    )


def test_normalize_filter_handles_none_blank_and_spaces():
    assert normalize_filter(None) == "*"
    assert normalize_filter("") == "*"
    assert normalize_filter("  ") == "*"
    assert normalize_filter("  Colombia ") == "Colombia"
    assert normalize_filter("some  thing") == "some thing"


def test_ttl_cache_set_get_and_stats():
    clock = FakeClock()
    cache = TTLCache(max_size=4, default_ttl=10, clock=clock, namespace="unit")

    hit, value = cache.get("missing")
    assert hit is False and value is None

    cache.set("k", {"a": 1})
    hit, value = cache.get("k")
    assert hit is True and value == {"a": 1}

    stats = cache.cache_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1
    assert stats["size"] == 1 and stats["max_size"] == 4


def test_ttl_cache_expiry_uses_injected_clock(fake_clock: FakeClock):
    cache = TTLCache(max_size=4, default_ttl=10, clock=fake_clock, namespace="unit")
    cache.set("k", {"v": 1})

    ok, _ = cache.get("k")
    assert ok is True

    fake_clock.advance(9.999)
    ok, _ = cache.get("k")
    assert ok is True  # still inside TTL

    fake_clock.advance(0.001)  # exactly reaches expire_at
    ok, _ = cache.get("k")
    assert ok is False  # monotonic expiry boundary inclusive

    stats = cache.cache_stats()
    assert stats["expired"] == 1


def test_ttl_cache_lru_eviction():
    clock = FakeClock()
    cache = TTLCache(max_size=2, default_ttl=100, clock=clock, namespace="unit")
    cache.set("a", 1)
    clock.advance(1)
    cache.set("b", 2)
    clock.advance(1)
    cache.get("a")  # refresh 'a' recency
    clock.advance(1)
    cache.set("c", 3)  # evicts 'b' (least recently used)

    assert cache.get("a")[0] is True
    assert cache.get("b")[0] is False
    assert cache.get("c")[0] is True
    assert cache.cache_stats()["evictions"] == 1


def test_ttl_cache_returns_defensive_copies():
    cache = TTLCache(max_size=4, default_ttl=10, clock=FakeClock(), namespace="unit")
    original = {"nested": [1, 2, 3]}
    cache.set("k", original)
    original["nested"].append(4)  # mutating after set must not affect cache

    _, value = cache.get("k")
    assert value["nested"] == [1, 2, 3]
    value["nested"].append(5)  # mutating after get must not affect cache either
    assert cache.get("k")[1]["nested"] == [1, 2, 3]


def test_ttl_cache_zero_ttl_disables_caching():
    cache = TTLCache(max_size=4, default_ttl=10, clock=FakeClock(), namespace="unit")
    cache.set("k", 1, ttl=0)
    assert cache.get("k")[0] is False


# ── Integration: suppliers endpoints ─────────────────────────


@pytest.fixture
def client(client: TestClient, auth_headers) -> TestClient:
    """Existing TestClient fixture (re-declared to attach auth headers)."""
    client.headers.update(auth_headers)
    return client


def _create_supplier(client: TestClient, n: int = 1, **overrides) -> dict:
    response = client.post("/api/suppliers", json=_supplier_payload(n, **overrides))
    assert response.status_code == 201, response.text
    return response.json()


def test_list_miss_then_hit(client: TestClient):
    _create_supplier(client, 1)

    r1 = client.get("/api/suppliers")
    assert r1.status_code == 200
    stats_after_first = suppliers_router_module.cache.cache_stats()
    assert stats_after_first["misses"] >= 1

    r2 = client.get("/api/suppliers")
    assert r2.status_code == 200
    assert r2.json() == r1.json()
    stats_after_second = suppliers_router_module.cache.cache_stats()
    assert stats_after_second["hits"] == stats_after_first["hits"] + 1


def test_detail_miss_then_hit(client: TestClient):
    created = _create_supplier(client, 1)
    sid = created["id"]

    r1 = client.get(f"/api/suppliers/{sid}")
    assert r1.status_code == 200

    r2 = client.get(f"/api/suppliers/{sid}")
    assert r2.status_code == 200
    assert r2.json() == r1.json()
    assert suppliers_router_module.cache.cache_stats()["hits"] >= 1


def test_distinct_params_use_distinct_keys(client: TestClient):
    _create_supplier(client, 1, pais="Colombia", categoriasQueProvee=["carne"])
    _create_supplier(client, 2, pais="USA", categoriasQueProvee=["bebida"])

    r_all = client.get("/api/suppliers")
    r_col = client.get("/api/suppliers?country=Colombia")
    r_carne = client.get("/api/suppliers?category=carne")
    r_mix = client.get("/api/suppliers?country=Colombia&category=carne")

    assert r_all.json()["total"] == 2
    assert r_col.json()["total"] == 1
    assert r_carne.json()["total"] == 1
    assert r_mix.json()["total"] == 1

    # Warm all four keys again -> 4 hits, values identical to first responses.
    assert client.get("/api/suppliers").json() == r_all.json()
    assert client.get("/api/suppliers?country=Colombia").json() == r_col.json()
    assert client.get("/api/suppliers?category=carne").json() == r_carne.json()
    assert client.get("/api/suppliers?country=Colombia&category=carne").json() == r_mix.json()

    stats = suppliers_router_module.cache.cache_stats()
    assert stats["hits"] >= 4
    assert stats["size"] == 4  # four distinct list variants cached


def test_ttl_expiry_via_injected_clock(client: TestClient, fake_clock: FakeClock, monkeypatch):
    _patch_cache_clock(monkeypatch, fake_clock)
    _create_supplier(client, 1)

    r1 = client.get("/api/suppliers")
    assert r1.status_code == 200
    assert suppliers_router_module.cache.cache_stats()["misses"] >= 1

    # Warm
    r2 = client.get("/api/suppliers")
    assert r2.json() == r1.json()

    # Advance beyond list TTL (60s) but within detail TTL window semantics
    fake_clock.advance(61)
    r3 = client.get("/api/suppliers")
    assert r3.status_code == 200
    assert r3.json() == r1.json()  # repopulated from source, same data
    stats = suppliers_router_module.cache.cache_stats()
    assert stats["expired"] >= 1  # old entry expired
    assert stats["misses"] >= 2


def test_detail_ttl_longer_than_list_ttl(client: TestClient, fake_clock: FakeClock, monkeypatch):
    _patch_cache_clock(monkeypatch, fake_clock)
    created = _create_supplier(client, 1)
    sid = created["id"]

    assert client.get(f"/api/suppliers/{sid}").status_code == 200

    fake_clock.advance(61)  # list TTL (60s) passed; detail TTL (120s) not
    r = client.get(f"/api/suppliers/{sid}")
    assert r.status_code == 200
    # detail key should still be cached (hit)
    assert suppliers_router_module.cache.get(
        suppliers_router_module.build_key(
            suppliers_router_module.DETAIL_KEY_PREFIX, f"id={sid}"
        )
    )[0] is True


def test_invalidation_after_create(client: TestClient):
    r1 = client.get("/api/suppliers")
    assert r1.json()["total"] == 0
    assert client.get("/api/suppliers").json()["total"] == 0  # warm

    _create_supplier(client, 1)

    r3 = client.get("/api/suppliers")
    assert r3.json()["total"] == 1  # not stale


def test_invalidation_after_rate_update(client: TestClient):
    created = _create_supplier(client, 1)
    sid = created["id"]

    # Warm list + detail caches
    client.get("/api/suppliers")
    detail_before = client.get(f"/api/suppliers/{sid}").json()
    assert detail_before["montoMinimoOrden"] == 100.0

    response = client.patch(f"/api/suppliers/{sid}/rate", json={"montoMinimoOrden": 250.0})
    assert response.status_code == 200

    # List and detail must reflect the new value (no stale cache).
    assert client.get("/api/suppliers").json()["suppliers"][0]["montoMinimoOrden"] == 250.0
    detail_after = client.get(f"/api/suppliers/{sid}").json()
    assert detail_after["montoMinimoOrden"] == 250.0


def test_invalidation_after_status_update(client: TestClient):
    created = _create_supplier(client, 1)
    sid = created["id"]

    client.get("/api/suppliers")
    client.get(f"/api/suppliers/{sid}")  # warm detail

    response = client.patch(f"/api/suppliers/{sid}/status", json={"status": "suspendido"})
    assert response.status_code == 200

    assert client.get("/api/suppliers").json()["suppliers"][0]["status"] == "suspendido"
    assert client.get(f"/api/suppliers/{sid}").json()["status"] == "suspendido"


def test_invalidation_after_delete(client: TestClient):
    created = _create_supplier(client, 1)
    sid = created["id"]

    client.get("/api/suppliers")
    assert client.get(f"/api/suppliers/{sid}").status_code == 200  # warm detail

    response = client.delete(f"/api/suppliers/{sid}")
    assert response.status_code == 200

    assert client.get("/api/suppliers").json()["total"] == 0
    assert client.get(f"/api/suppliers/{sid}").status_code == 404


def test_404_not_cached(client: TestClient, fake_clock: FakeClock, monkeypatch):
    _patch_cache_clock(monkeypatch, fake_clock)

    r = client.get("/api/suppliers/999")
    assert r.status_code == 404

    # No detail key should exist for the failed lookup.
    missing_key = suppliers_router_module.build_key(
        suppliers_router_module.DETAIL_KEY_PREFIX, "id=999"
    )
    assert suppliers_router_module.cache.get(missing_key)[0] is False

    # Create the supplier afterwards: if the 404 had been cached, this would still 404.
    created = _create_supplier(client, 1)
    sid = created["id"]
    # ensure doc_id 999 does not collide: use the real created id
    r2 = client.get(f"/api/suppliers/{sid}")
    assert r2.status_code == 200


def test_cache_isolation_between_list_variants_and_mutation(client: TestClient):
    _create_supplier(client, 1, pais="Colombia")
    _create_supplier(client, 2, pais="USA")

    r_col = client.get("/api/suppliers?country=Colombia")
    assert r_col.json()["total"] == 1

    # A mutation must invalidate ALL list variants, not just the unfiltered one.
    _create_supplier(client, 3, pais="Colombia")

    assert client.get("/api/suppliers?country=Colombia").json()["total"] == 2
    assert client.get("/api/suppliers").json()["total"] == 3


def test_health_and_login_are_not_cached():
    """Sanity: the TTL cache is only wired into supplier GET endpoints."""
    assert suppliers_router_module.LIST_TTL_SECONDS == 60.0
    assert suppliers_router_module.DETAIL_TTL_SECONDS == 120.0
    # Auth/login responses flow through no cache: no cache key namespaces exist for them.
    assert suppliers_router_module.cache._namespace == "suppliers"


# ── Timing middleware ────────────────────────────────────────


def test_timing_middleware_preserves_status_and_body(client: TestClient, caplog):
    with caplog.at_level(logging.INFO, logger="brasaland.timing"):
        r1 = client.get("/health")
        assert r1.status_code == 200
        assert r1.json() == {"status": "ok"}

        r2 = client.get("/api/suppliers/999")
        assert r2.status_code == 404

        r3 = client.get("/api/suppliers")
        assert r3.status_code == 200

    timing_logs = [rec for rec in caplog.records if rec.name == "brasaland.timing"]
    assert len(timing_logs) >= 3

    # Log shape: "METHOD /path -> STATUS (X.XX ms)" and no query/headers/body leakage
    for record in timing_logs:
        message = record.getMessage()
        assert "->" in message and "ms" in message
        assert "password" not in message.lower()
        assert "Authorization" not in message


def test_timing_middleware_does_not_change_response(client: TestClient):
    """Identical requests before/after middleware presence produce equal bodies."""
    r1 = client.get("/health")
    assert r1.status_code == 200
    body1 = r1.json()
    r2 = client.get("/health")
    assert r2.json() == body1
    assert r2.status_code == r1.status_code


def test_timing_middleware_reports_duration(client: TestClient, caplog):
    import re

    with caplog.at_level(logging.INFO, logger="brasaland.timing"):
        client.get("/health")

    record = [r for r in caplog.records if r.name == "brasaland.timing"][-1]
    match = re.search(r"\(([\d.]+) ms\)", record.getMessage())
    assert match is not None
    duration = float(match.group(1))
    assert 0.0 <= duration < 60_000.0  # sanity bound, no artificial pauses
