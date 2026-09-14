"""seed.py — Brasaland · Datos semilla idempotentes para PostgreSQL y MongoDB.

Idempotencia: cada fila se inserta SOLO si no existe su clave natural
(codigo / nombre / email / plato). Ejecutar el script N veces produce
el mismo estado final (no duplicados, no sobrescribe datos del usuario).

Uso:
    uv run python scripts/seed.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

# Permitir ejecución directa: python scripts/seed.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.common.security import hash_password
from app.database import SessionLocal
from app.domains.auth.models import Usuario
from app.domains.ingredients.models import (
    Ingrediente,
    InventarioLocal,
    MovimientoInventario,
)
from app.domains.locations.models import Local
from app.domains.procurement.models import LocalProveedor, Proveedor
from app.mongo import connect_mongo, close_mongo, get_recetas_collection, get_auditoria_collection

# ----------------------------------------------------------------------------
# Datos semilla
# ----------------------------------------------------------------------------

LOCALES = [
    {"nombre": "Brasaland Chapinero", "ciudad": "Bogotá", "pais": "CO", "direccion": "Calle 65 #12-30"},
    {"nombre": "Brasaland Norte", "ciudad": "Bogotá", "pais": "CO", "direccion": "Autopista Norte #118-45"},
    {"nombre": "Brasaland Medellín", "ciudad": "Medellín", "pais": "CO", "direccion": "Carrera 43A #10-25"},
    {"nombre": "Brasaland Cali", "ciudad": "Cali", "pais": "CO", "direccion": "Avenida 6N #28-50"},
    {"nombre": "Brasaland Miami", "ciudad": "Miami", "pais": "US", "direccion": "2200 SW 8th St"},
    {"nombre": "Brasaland Orlando", "ciudad": "Orlando", "pais": "US", "direccion": "8101 International Dr"},
]

PROVEEDORES = [
    {"nombre": "Carnes del Valle S.A.", "pais": "CO", "dias_entrega": 2, "contacto_email": "ventas@carnesvalle.co"},
    {"nombre": "Verduras Andinas", "pais": "CO", "dias_entrega": 1, "contacto_email": "pedidos@verdurasandinas.co"},
    {"nombre": "Lácteos La Sabana", "pais": "CO", "dias_entrega": 2, "contacto_email": "comercial@lasabana.co"},
    {"nombre": "Miami Food Distributors", "pais": "US", "dias_entrega": 4, "contacto_email": "sales@miamifood.com"},
    {"nombre": "Frutas Tropicales SA", "pais": "CO", "dias_entrega": 3, "contacto_email": "hola@frutastropicales.co"},
]

INGREDIENTES = [
    {"codigo": "CAR-001", "nombre": "Churrasco de res", "unidad": "kg", "stock_minimo": 40, "costo_unitario": "38500", "moneda": "COP", "proveedor": "Carnes del Valle S.A."},
    {"codigo": "CAR-002", "nombre": "Pechuga de pollo", "unidad": "kg", "stock_minimo": 30, "costo_unitario": "16900", "moneda": "COP", "proveedor": "Carnes del Valle S.A."},
    {"codigo": "CAR-003", "nombre": "Costillas de cerdo", "unidad": "kg", "stock_minimo": 25, "costo_unitario": "22000", "moneda": "COP", "proveedor": "Carnes del Valle S.A."},
    {"codigo": "VER-001", "nombre": "Tomate chonto", "unidad": "kg", "stock_minimo": 20, "costo_unitario": "4800", "moneda": "COP", "proveedor": "Verduras Andinas"},
    {"codigo": "VER-002", "nombre": "Cebolla junca", "unidad": "kg", "stock_minimo": 15, "costo_unitario": "6200", "moneda": "COP", "proveedor": "Verduras Andinas"},
    {"codigo": "VER-003", "nombre": "Aguacate hass", "unidad": "kg", "stock_minimo": 18, "costo_unitario": "11000", "moneda": "COP", "proveedor": "Frutas Tropicales SA"},
    {"codigo": "LAC-001", "nombre": "Queso campesino", "unidad": "kg", "stock_minimo": 12, "costo_unitario": "17500", "moneda": "COP", "proveedor": "Lácteos La Sabana"},
    {"codigo": "LAC-002", "nombre": "Crema de leche", "unidad": "L", "stock_minimo": 10, "costo_unitario": "9800", "moneda": "COP", "proveedor": "Lácteos La Sabana"},
    {"codigo": "BEB-001", "nombre": "Limonada base", "unidad": "L", "stock_minimo": 25, "costo_unitario": "3500", "moneda": "COP", "proveedor": "Frutas Tropicales SA"},
    {"codigo": "BEB-002", "nombre": "Chicken wings IQF", "unidad": "kg", "stock_minimo": 35, "costo_unitario": "6.20", "moneda": "USD", "proveedor": "Miami Food Distributors"},
]

# (local, ingrediente, cantidad_actual, cantidad_minima)
INVENTARIO = [
    ("Brasaland Chapinero", "CAR-001", 120.5, 40),
    ("Brasaland Chapinero", "CAR-002", 28.0, 30),   # ALERTA: por debajo del mínimo
    ("Brasaland Chapinero", "VER-001", 45.0, 20),
    ("Brasaland Chapinero", "LAC-001", 9.5, 12),    # ALERTA
    ("Brasaland Chapinero", "BEB-001", 60.0, 25),
    ("Brasaland Norte", "CAR-001", 55.0, 40),
    ("Brasaland Norte", "CAR-003", 18.0, 15),
    ("Brasaland Norte", "VER-002", 12.0, 15),       # ALERTA
    ("Brasaland Norte", "LAC-002", 22.0, 10),
    ("Brasaland Norte", "BEB-001", 31.0, 25),
    ("Brasaland Medellín", "CAR-002", 47.0, 30),
    ("Brasaland Medellín", "VER-002", 30.0, 15),
    ("Brasaland Medellín", "VER-003", 14.0, 12),
    ("Brasaland Medellín", "LAC-001", 20.0, 12),
    ("Brasaland Cali", "CAR-001", 8.0, 40),         # ALERTA
    ("Brasaland Cali", "CAR-003", 25.0, 15),
    ("Brasaland Cali", "VER-001", 18.0, 20),        # ALERTA
    ("Brasaland Cali", "LAC-002", 15.0, 10),
    ("Brasaland Miami", "BEB-002", 60.0, 35),
    ("Brasaland Miami", "LAC-002", 8.0, 10),
    ("Brasaland Orlando", "BEB-002", 30.0, 35),     # ALERTA
    ("Brasaland Orlando", "BEB-001", 12.0, 25),     # ALERTA
]

# (local, ingrediente, tipo, cantidad, dias_atras)
MOVIMIENTOS = [
    ("Brasaland Chapinero", "CAR-001", "entrada", 100.0, 20),
    ("Brasaland Chapinero", "CAR-001", "salida", 60.0, 15),
    ("Brasaland Chapinero", "CAR-001", "entrada", 80.5, 7),
    ("Brasaland Chapinero", "CAR-002", "entrada", 50.0, 12),
    ("Brasaland Chapinero", "CAR-002", "salida", 22.0, 9),
    ("Brasaland Norte", "CAR-001", "entrada", 75.0, 18),
    ("Brasaland Norte", "CAR-001", "salida", 20.0, 11),
    ("Brasaland Norte", "LAC-002", "entrada", 30.0, 6),
    ("Brasaland Norte", "BEB-001", "salida", 14.0, 3),
    ("Brasaland Medellín", "CAR-002", "entrada", 62.0, 10),
    ("Brasaland Medellín", "VER-002", "entrada", 45.0, 5),
    ("Brasaland Medellín", "VER-002", "salida", 15.0, 2),
    ("Brasaland Cali", "CAR-001", "salida", 42.0, 4),   # salidas que explican el stock bajo
    ("Brasaland Cali", "VER-001", "salida", 27.0, 2),
    ("Brasaland Orlando", "BEB-001", "salida", 13.0, 1),
]

RECETAS = [
    {
        "plato": "Churrasco a la brasa",
        "categoria": "carnes",
        "porciones": 4,
        "ingredientes": [
            {"ingrediente_id": "CAR-001", "nombre": "Churrasco de res", "cantidad": 1.6, "unidad": "kg"},
            {"ingrediente_id": "VER-002", "nombre": "Cebolla junca", "cantidad": 0.3, "unidad": "kg"},
            {"ingrediente_id": "VER-003", "nombre": "Aguacate hass", "cantidad": 0.4, "unidad": "kg"},
        ],
        "pasos": [
            {"orden": 1, "descripcion": "Marinar el churrasco con sal, pimienta y aceite por 30 minutos.", "duracion_min": 30},
            {"orden": 2, "descripcion": "Asar a fuego alto 6 minutos por lado según el punto deseado.", "duracion_min": 12},
            {"orden": 3, "descripcion": "Reposar 5 minutos antes de cortar contra la fibra.", "duracion_min": 5},
        ],
        "tags": ["parrilla", "res", "estrella"],
    },
    {
        "plato": "Alitas BBQ glaseadas",
        "categoria": "carnes",
        "porciones": 6,
        "ingredientes": [
            {"ingrediente_id": "BEB-002", "nombre": "Chicken wings IQF", "cantidad": 2.2, "unidad": "kg"},
            {"ingrediente_id": "VER-001", "nombre": "Tomate chonto", "cantidad": 0.2, "unidad": "kg"},
        ],
        "pasos": [
            {"orden": 1, "descripcion": "Hornear las alitas congeladas a 200°C por 25 minutos.", "duracion_min": 25},
            {"orden": 2, "descripcion": "Bañar en salsa BBQ y glasear 8 minutos más.", "duracion_min": 8},
        ],
        "tags": ["alitas", "bbq", "shared"],
    },
    {
        "plato": "Limonada de coco",
        "categoria": "bebidas",
        "porciones": 8,
        "ingredientes": [
            {"ingrediente_id": "BEB-001", "nombre": "Limonada base", "cantidad": 1.5, "unidad": "L"},
            {"ingrediente_id": "LAC-002", "nombre": "Crema de leche", "cantidad": 0.25, "unidad": "L"},
        ],
        "pasos": [
            {"orden": 1, "descripcion": "Licuar la limonada base con hielo y crema de leche.", "duracion_min": 4},
            {"orden": 2, "descripcion": "Servir en vaso alto con bordes de azúcar.", "duracion_min": 2},
        ],
        "tags": ["bebida", "postre", "verano"],
    },
]

USUARIOS = [
    {"email": "admin@brasaland.com", "password": "admin123", "nombre": "Administrador General", "rol": "admin"},
    {"email": "operador@brasaland.com", "password": "operador123", "nombre": "Operador de Inventario", "rol": "operador"},
    {"email": "consulta@brasaland.com", "password": "consulta123", "nombre": "Analista de Consulta", "rol": "consulta"},
]

# ----------------------------------------------------------------------------
# Helpers de idempotencia
# ----------------------------------------------------------------------------


def sembrar_locales(db) -> dict[str, Local]:
    locales: dict[str, Local] = {}
    for data in LOCALES:
        local = db.query(Local).filter_by(nombre=data["nombre"]).first()
        if local is None:
            local = Local(**data)
            db.add(local)
            db.flush()
            print(f"  + local: {local.nombre} ({local.pais}, {local.moneda})")
        locales[data["nombre"]] = local
    db.commit()
    return locales


def sembrar_proveedores(db) -> dict[str, Proveedor]:
    proveedores: dict[str, Proveedor] = {}
    for data in PROVEEDORES:
        prov = db.query(Proveedor).filter_by(nombre=data["nombre"]).first()
        if prov is None:
            prov = Proveedor(
                nombre=data["nombre"],
                pais=data["pais"],
                dias_entrega=data["dias_entrega"],
                contacto=data["contacto_email"],
            )
            db.add(prov)
            db.flush()
            print(f"  + proveedor: {prov.nombre} ({prov.pais})")
        proveedores[data["nombre"]] = prov
    db.commit()
    return proveedores


def sembrar_vinculos(db, locales, proveedores) -> None:
    """N:M locales-proveedores con lead time y precio acordado."""
    vinculos = [
        ("Carnes del Valle S.A.", ["Brasaland Chapinero", "Brasaland Norte", "Brasaland Medellín", "Brasaland Cali"], True),
        ("Verduras Andinas", ["Brasaland Chapinero", "Brasaland Norte", "Brasaland Medellín"], False),
        ("Lácteos La Sabana", ["Brasaland Chapinero", "Brasaland Cali"], False),
        ("Frutas Tropicales SA", ["Brasaland Medellín", "Brasaland Cali"], False),
        ("Miami Food Distributors", ["Brasaland Miami", "Brasaland Orlando"], True),
    ]
    for prov_nombre, local_nombres, es_principal in vinculos:
        prov = proveedores[prov_nombre]
        for ln in local_nombres:
            existe = (
                db.query(LocalProveedor)
                .filter_by(local_id=locales[ln].id, proveedor_id=prov.id)
                .first()
            )
            if existe is None:
                db.add(
                    LocalProveedor(
                        local_id=locales[ln].id,
                        proveedor_id=prov.id,
                        es_principal=es_principal,
                        lead_time_dias=prov.dias_entrega,
                    )
                )
                print(f"  + vinculo: {prov.nombre} <-> {ln}")
    db.commit()


def sembrar_ingredientes(db, proveedores) -> dict[str, Ingrediente]:
    ingredientes: dict[str, Ingrediente] = {}
    for data in INGREDIENTES:
        ing = db.query(Ingrediente).filter_by(codigo=data["codigo"]).first()
        if ing is None:
            prov = proveedores.get(data["proveedor"])
            ing = Ingrediente(
                codigo=data["codigo"],
                nombre=data["nombre"],
                unidad=data["unidad"],
                stock_minimo=Decimal(data["stock_minimo"]),
                costo_unitario=Decimal(data["costo_unitario"]),
                moneda=data["moneda"],
                proveedor_id=prov.id if prov else None,
                activo=True,
            )
            db.add(ing)
            db.flush()
            print(f"  + ingrediente: {ing.codigo} {ing.nombre}")
        ingredientes[data["codigo"]] = ing
    db.commit()
    return ingredientes


def sembrar_inventario(db, locales, ingredientes) -> None:
    for local_nombre, codigo, actual, minimo in INVENTARIO:
        local = locales[local_nombre]
        ing = ingredientes[codigo]
        row = db.query(InventarioLocal).filter_by(local_id=local.id, ingrediente_id=ing.id).first()
        if row is None:
            db.add(
                InventarioLocal(
                    local_id=local.id,
                    ingrediente_id=ing.id,
                    cantidad_actual=Decimal(str(actual)),
                    cantidad_minima=Decimal(str(minimo)),
                )
            )
            try:
                db.flush()  # valida UNIQUE(local, ingrediente) fila por fila
                print(f"  + inventario: {local_nombre} · {codigo} = {actual} (min {minimo})")
            except Exception:
                db.rollback()
                print(f"  ! inventario duplicado omitido: {local_nombre} · {codigo}")
    db.commit()


def sembrar_movimientos(db, locales, ingredientes) -> None:
    ahora = datetime.now(timezone.utc)
    filas = 0
    for local_nombre, codigo, tipo, cantidad, dias_atras in MOVIMIENTOS:
        local = locales[local_nombre]
        ing = ingredientes[codigo]
        inv = db.query(InventarioLocal).filter_by(local_id=local.id, ingrediente_id=ing.id).first()
        if inv is None:
            continue
        creado = ahora - timedelta(days=dias_atras)
        # Idempotencia determinista: motivo único por movimiento sembrado
        motivo = f"seed:{local_nombre}:{codigo}:{tipo}:{dias_atras}d"
        if db.query(MovimientoInventario).filter_by(motivo=motivo).first() is not None:
            continue
        db.add(
            MovimientoInventario(
                inventario_local_id=inv.id,
                tipo=tipo,
                cantidad=Decimal(str(cantidad)),
                motivo=motivo,
                created_at=creado,
            )
        )
        filas += 1
    if filas:
        print(f"  + {filas} movimiento(s) de inventario (kardex)")
    db.commit()


def sembrar_recetas(ingredientes) -> None:
    """Inserta recetas anidadas; resuelve ingrediente_id (código) al ID real de PostgreSQL."""
    col = get_recetas_collection()
    for receta in RECETAS:
        if col.find_one({"plato": receta["plato"]}) is None:
            doc = dict(receta)
            doc["ingredientes"] = [
                {
                    "ingrediente_id": ingredientes[cod].id,  # FK real a PostgreSQL
                    "codigo": cod,  # denormalizado para legibilidad
                    "nombre": i["nombre"],
                    "cantidad": i["cantidad"],
                    "unidad": i["unidad"],
                }
                for i in receta["ingredientes"]
                for cod in [i["ingrediente_id"]]
            ]
            doc["created_at"] = datetime.now(timezone.utc)
            col.insert_one(doc)
            print(f"  + receta (Mongo): {receta['plato']}")
    print(f"  total recetas: {col.count_documents({})}")


def sembrar_usuarios(db) -> None:
    for data in USUARIOS:
        if db.query(Usuario).filter_by(email=data["email"]).first() is None:
            db.add(
                Usuario(
                    email=data["email"],
                    nombre=data["nombre"],
                    hashed_password=hash_password(data["password"]),
                    rol=data["rol"],
                    activo=True,
                )
            )
            print(f"  + usuario: {data['email']} ({data['rol']})")
    db.commit()


def main() -> None:
    print("== Seed Brasaland ==")
    connect_mongo()
    db = SessionLocal()
    try:
        locales = sembrar_locales(db)
        proveedores = sembrar_proveedores(db)
        sembrar_vinculos(db, locales, proveedores)
        ingredientes = sembrar_ingredientes(db, proveedores)
        sembrar_inventario(db, locales, ingredientes)
        sembrar_movimientos(db, locales, ingredientes)
        sembrar_usuarios(db)
        sembrar_recetas(ingredientes)
        print("== Seed completado ==")
    finally:
        db.close()
        close_mongo()


if __name__ == "__main__":
    main()