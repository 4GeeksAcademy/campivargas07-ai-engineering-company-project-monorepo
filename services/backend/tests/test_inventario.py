"""test_inventario.py — Transacción de movimientos, kardex y alertas de reposición."""
from __future__ import annotations

from decimal import Decimal


def _crear_local(client, headers, nombre: str) -> int:
    r = client.post(
        "/api/v1/locales", headers=headers,
        json={"nombre": nombre, "ciudad": "Bogotá", "pais": "CO"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _crear_ingrediente(client, headers, codigo: str) -> int:
    r = client.post(
        "/api/v1/ingredientes", headers=headers,
        json={"codigo": codigo, "nombre": f"Ing {codigo}", "unidad": "kg",
              "stock_minimo": 10, "costo_unitario": "100", "moneda": "COP"},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_movimiento_entrada_actualiza_stock(client, auth_headers):
    """POST /inventario/movimientos (entrada) debe crear stock y devolver 201."""
    local_id = _crear_local(client, auth_headers, "Local Test Entrada")
    ing_id = _crear_ingrediente(client, auth_headers, "INV-E001")

    r = client.post(
        "/api/v1/inventario/movimientos", headers=auth_headers,
        json={"local_id": local_id, "ingrediente_id": ing_id, "tipo": "entrada",
              "cantidad": "50", "motivo": "compra inicial"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["movimiento"]["tipo"] == "entrada"
    assert body["movimiento"]["cantidad"] == "50.000"  # NUMERIC(12,3)
    assert body["inventario"]["cantidad_actual"] == "50.000"
    assert body["inventario"]["necesita_reposicion"] is False

    # Segunda entrada acumula
    r = client.post(
        "/api/v1/inventario/movimientos", headers=auth_headers,
        json={"local_id": local_id, "ingrediente_id": ing_id, "tipo": "entrada",
              "cantidad": "25", "motivo": "segunda compra"},
    )
    assert r.status_code == 201
    assert r.json()["inventario"]["cantidad_actual"] == "75.000"


def test_movimiento_salida_stock_insuficiente_400(client, auth_headers):
    """Regla de negocio: salida mayor al stock → 400, y el stock NO cambia."""
    local_id = _crear_local(client, auth_headers, "Local Test Salida")
    ing_id = _crear_ingrediente(client, auth_headers, "INV-S001")

    r = client.post(
        "/api/v1/inventario/movimientos", headers=auth_headers,
        json={"local_id": local_id, "ingrediente_id": ing_id, "tipo": "entrada",
              "cantidad": "10", "motivo": "carga"},
    )
    assert r.status_code == 201

    # Salida mayor al stock → 400
    r = client.post(
        "/api/v1/inventario/movimientos", headers=auth_headers,
        json={"local_id": local_id, "ingrediente_id": ing_id, "tipo": "salida",
              "cantidad": "999", "motivo": "salida imposible"},
    )
    assert r.status_code == 400

    # El stock quedó intacto (transacción atómica)
    r = client.get("/api/v1/inventario", params={"local_id": local_id})
    items = [i for i in r.json()["items"] if i["ingrediente_id"] == ing_id]
    assert len(items) == 1
    assert items[0]["cantidad_actual"] == "10.000"


def test_movimiento_ajuste(client, auth_headers):
    """Ajuste de inventario físico."""
    local_id = _crear_local(client, auth_headers, "Local Test Ajuste")
    ing_id = _crear_ingrediente(client, auth_headers, "INV-A001")
    client.post("/api/v1/inventario/movimientos", headers=auth_headers, json={
        "local_id": local_id, "ingrediente_id": ing_id, "tipo": "entrada", "cantidad": "20"})
    r = client.post("/api/v1/inventario/movimientos", headers=auth_headers, json={
        "local_id": local_id, "ingrediente_id": ing_id, "tipo": "ajuste", "cantidad": "18",
        "motivo": "conteo fisico"})
    assert r.status_code == 201
    assert r.json()["inventario"]["cantidad_actual"] == "18.000"


def test_kardex(client, auth_headers):
    """GET /inventario/{id}/movimientos devuelve el historial en orden."""
    local_id = _crear_local(client, auth_headers, "Local Test Kardex")
    ing_id = _crear_ingrediente(client, auth_headers, "INV-K001")
    client.post("/api/v1/inventario/movimientos", headers=auth_headers, json={
        "local_id": local_id, "ingrediente_id": ing_id, "tipo": "entrada", "cantidad": "30"})
    client.post("/api/v1/inventario/movimientos", headers=auth_headers, json={
        "local_id": local_id, "ingrediente_id": ing_id, "tipo": "salida", "cantidad": "12"})

    r = client.get("/api/v1/inventario", params={"local_id": local_id})
    inv = [i for i in r.json()["items"] if i["ingrediente_id"] == ing_id][0]
    r = client.get(f"/api/v1/inventario/{inv['id']}/movimientos")
    assert r.status_code == 200
    movs = r.json()
    assert len(movs) == 2
    assert {m["tipo"] for m in movs} == {"entrada", "salida"}


def test_alertas_incluyen_deficit(client, auth_headers, _pg_engine):
    """GET /inventario/alertas: JOIN local+ingrediente y deficit = min - actual."""
    from sqlalchemy import update
    from sqlalchemy.orm import sessionmaker

    from app.domains.inventory.models import InventarioLocal

    local_id = _crear_local(client, auth_headers, "Local Test Alerta")
    ing_id = _crear_ingrediente(client, auth_headers, "INV-AL001")
    # entrada de 3 → crea la fila de inventario (cantidad_minima arranca en 0)
    client.post("/api/v1/inventario/movimientos", headers=auth_headers, json={
        "local_id": local_id, "ingrediente_id": ing_id, "tipo": "entrada", "cantidad": "3"})

    # El mínimo por local se fija por administración (como hace el seed):
    # subimos cantidad_minima a 10 para provocar la alerta.
    Session = sessionmaker(bind=_pg_engine)
    db = Session()
    db.execute(
        update(InventarioLocal)
        .where(InventarioLocal.local_id == local_id, InventarioLocal.ingrediente_id == ing_id)
        .values(cantidad_minima=10)
    )
    db.commit()
    db.close()

    r = client.get("/api/v1/inventario/alertas")
    assert r.status_code == 200
    alerta = next((a for a in r.json() if a["local_id"] == local_id and a["ingrediente_id"] == ing_id), None)
    assert alerta is not None
    assert alerta["deficit"] == "7.000"
    assert alerta["ingrediente_codigo"] == "INV-AL001"
    assert alerta["local_nombre"].startswith("Local Test Alerta")


def test_movimiento_sin_token_401(client):
    r = client.post(
        "/api/v1/inventario/movimientos",
        json={"local_id": 1, "ingrediente_id": 1, "tipo": "entrada", "cantidad": "1"},
    )
    assert r.status_code == 401