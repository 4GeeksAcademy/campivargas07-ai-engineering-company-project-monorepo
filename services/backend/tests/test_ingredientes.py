"""test_ingredientes.py — CRUD de ingredientes (PostgreSQL) con JWT y códigos HTTP."""
from __future__ import annotations


def test_crud_ingrediente_completo(client, auth_headers):
    """Ciclo completo: crear → leer → actualizar → borrar lógico."""
    payload = {
        "codigo": "TST-001",
        "nombre": "Ingrediente de prueba",
        "unidad": "kg",
        "stock_minimo": 10,
        "costo_unitario": "1234.50",
        "moneda": "COP",
    }
    # CREATE → 201
    r = client.post("/api/v1/ingredientes", headers=auth_headers, json=payload)
    assert r.status_code == 201, r.text
    ing = r.json()
    ing_id = ing["id"]
    assert ing["codigo"] == "TST-001"
    assert ing["activo"] is True

    # READ → 200
    r = client.get(f"/api/v1/ingredientes/{ing_id}")
    assert r.status_code == 200
    assert r.json()["nombre"] == "Ingrediente de prueba"

    # UPDATE → 200
    r = client.put(f"/api/v1/ingredientes/{ing_id}", headers=auth_headers, json={"costo_unitario": "1500.00"})
    assert r.status_code == 200
    assert r.json()["costo_unitario"] == "1500.00"

    # DELETE → 200 con cuerpo (sin inventario: borrado físico)
    r = client.delete(f"/api/v1/ingredientes/{ing_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["eliminado"] is True

    # GET después de borrar físicamente → 404
    r = client.get(f"/api/v1/ingredientes/{ing_id}")
    assert r.status_code == 404


def test_delete_ingrediente_con_inventario_es_borrado_logico(client, auth_headers):
    """Un ingrediente con historial de inventario se desactiva (no se borra)."""
    # El seed crea CAR-001 con inventario; no lo borramos: usamos uno propio
    payload = {
        "codigo": "TST-LOG",
        "nombre": "Con inventario",
        "unidad": "kg",
        "stock_minimo": 5,
        "costo_unitario": "10",
        "moneda": "COP",
    }
    ing = client.post("/api/v1/ingredientes", headers=auth_headers, json=payload).json()
    ing_id = ing["id"]

    # Crear un local y stock para forzar borrado lógico
    local = client.post(
        "/api/v1/locales", headers=auth_headers,
        json={"nombre": "Local Test Logico", "ciudad": "Bogotá", "pais": "CO"},
    ).json()

    r = client.post(
        "/api/v1/inventario/movimientos", headers=auth_headers,
        json={"local_id": local["id"], "ingrediente_id": ing_id, "tipo": "entrada",
              "cantidad": "25", "motivo": "carga inicial test"},
    )
    assert r.status_code == 201, r.text

    # DELETE → borrado lógico (200, modo logico)
    r = client.delete(f"/api/v1/ingredientes/{ing_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["modo"] == "borrado_logico"

    # El registro sigue existiendo (desactivado) — validar en listado con filtro
    r = client.get("/api/v1/ingredientes", params={"search": "TST-LOG"})
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["activo"] is False


def test_crear_ingrediente_codigo_duplicado_400(client, auth_headers):
    """Código UNIQUE en BD: duplicado → 400 con mensaje claro."""
    payload = {
        "codigo": "TST-DUP",
        "nombre": "Duplicado",
        "unidad": "kg",
        "stock_minimo": 1,
        "costo_unitario": "1",
        "moneda": "COP",
    }
    r1 = client.post("/api/v1/ingredientes", headers=auth_headers, json=payload)
    assert r1.status_code == 201
    r2 = client.post("/api/v1/ingredientes", headers=auth_headers, json=payload)
    assert r2.status_code == 400


def test_crear_ingrediente_proveedor_inexistente_400(client, auth_headers):
    r = client.post(
        "/api/v1/ingredientes",
        headers=auth_headers,
        json={
            "codigo": "TST-FK",
            "nombre": "FK invalida",
            "unidad": "kg",
            "stock_minimo": 1,
            "costo_unitario": "1",
            "moneda": "COP",
            "proveedor_id": 99999,
        },
    )
    assert r.status_code == 400


def test_ingredientes_sin_token_401(client):
    r = client.post(
        "/api/v1/ingredientes",
        json={
            "codigo": "TST-401",
            "nombre": "Sin token",
            "unidad": "kg",
            "stock_minimo": 1,
            "costo_unitario": "1",
            "moneda": "COP",
        },
    )
    assert r.status_code == 401


def test_listado_paginado(client):
    r = client.get("/api/v1/ingredientes", params={"page": 1, "size": 5})
    assert r.status_code == 200
    body = r.json()
    assert {"items", "total", "page", "size", "pages"} <= set(body.keys())
    assert len(body["items"]) <= 5