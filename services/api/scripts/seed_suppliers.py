"""
seed_suppliers.py — Brasaland · Bulk supplier seed for performance measurements

Generates a configurable volume of varied, schema-valid suppliers in an
ISOLATED TinyDB file so that performance baselines and post-optimisation
measurements are realistic.

Safety (per task spec):
- NEVER touches ``services/api/data/suppliers.json``.
- Target file is passed via ``--out`` (e.g. /tmp/brasa-seed/suppliers.json)
  or ``SUPPLIERS_DB_PATH`` env var; refuses to write to the repo data dir.
- Idempotent: re-running truncates the suppliers table of the target file and
  regenerates deterministically (fixed RNG seed), so before/after datasets
  are byte-identical in content.

Usage (from services/api):
    uv run python scripts/seed_suppliers.py --out /tmp/brasa-seed/suppliers.json --count 5000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_DATA_FILE = Path(__file__).resolve().parents[1] / "data" / "suppliers.json"

PAISES = ["Colombia", "USA"]
MONEDAS = ["COP", "USD"]
CATEGORIAS = ["carne", "verdura", "salsa", "bebida", "empaque", "limpieza"]
STATUSES = ["activo", "activo", "activo", "suspendido"]  # ~75% activo

NOMBRES_BASE = [
    "Carnes del Valle", "Verduras La Finca", "Salsas del Caribe",
    "Bebidas Andinas", "Empaques Rápidos", "Limpieza Total",
    "Distribuidora El Sabor", "Agregados Norte", "Comercial Brasa",
    "Ingredientes Global", "Fresco Andino", "La Bodega del Chef",
]
CONTACTOS = [
    "María Gómez", "Carlos Ruiz", "Ana Torres", "Luis Peña", "Sofía Marín",
    "Jorge Salas", "Paula Ortiz", "Andrés Vélez", "Camila Restrepo",
    "Diego Fajardo", "Laura Cano", "Pedro Navarro",
]
DOMINIOS = ["proveedores-brasaland.com", "suministros.co", " distributors.com", "gmail.com"]


def build_suppliers(count: int, seed: int = 42) -> list[dict]:
    """Deterministically generate ``count`` schema-valid supplier documents."""
    rng = random.Random(seed)
    docs: list[dict] = []
    for i in range(1, count + 1):
        nombre_base = NOMBRES_BASE[i % len(NOMBRES_BASE)]
        pais = PAISES[i % len(PAISES)]
        num_categorias = rng.randint(1, 6)
        categorias = rng.sample(CATEGORIAS, num_categorias)
        moneda = "COP" if pais == "Colombia" else rng.choice(MONEDAS)
        doc = {
            "nombre": f"{nombre_base} #{i:05d}",
            "pais": pais,
            "contactoNombre": rng.choice(CONTACTOS),
            "contactoEmail": f"contacto{i:05d}@{DOMINIOS[i % len(DOMINIOS)].strip()}",
            "contactoTelefono": f"+{57 if pais == 'Colombia' else 1} 300 {rng.randint(1000000, 9999999)}",
            "categoriasQueProvee": categorias,
            "tiempoEntregaDias": rng.randint(1, 30),
            "montoMinimoOrden": round(rng.uniform(50, 5000), 2),
            "moneda": moneda,
            "status": STATUSES[i % len(STATUSES)],
        }
        docs.append(doc)
    return docs


def write_seed(path: Path, count: int, seed: int) -> Path:
    """Write the seed database. Refuses to touch the repo runtime data file."""
    path = path.resolve()
    if path == REPO_DATA_FILE.resolve():
        print(
            f"ERROR: refusing to write to the repo runtime DB ({REPO_DATA_FILE}).\n"
            "Use a temp/scratch path instead, e.g. /tmp/brasa-seed/suppliers.json",
            file=sys.stderr,
        )
        sys.exit(2)

    path.parent.mkdir(parents=True, exist_ok=True)
    docs = build_suppliers(count, seed)

    # TinyDB stores every table as a mapping "doc_id -> document". Write the
    # suppliers table in that exact shape so app.database can load the file
    # directly without a conversion pass. Each doc also embeds "doc_id"
    # because suppliers service resolves detail/update by that field.
    for i, doc in enumerate(docs):
        doc["doc_id"] = i + 1
    payload = {
        "suppliers": {str(i + 1): doc for i, doc in enumerate(docs)},
        "users": {},
        "profiles": {},
        "_default": {},
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)

    print(f"OK: wrote {count} suppliers to {path}")
    print(f"    tables: suppliers ({len(docs)} docs), users/profiles empty")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed bulk suppliers into an isolated TinyDB file.")
    parser.add_argument(
        "--out",
        default=None,
        help="Target TinyDB JSON path (default: $SUPPLIERS_DB_PATH). Must NOT be the repo data file.",
    )
    parser.add_argument("--count", type=int, default=5000, help="Number of suppliers to generate")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (deterministic datasets)")
    args = parser.parse_args()

    target = args.out or __import__("os").environ.get("SUPPLIERS_DB_PATH")
    if not target:
        print("ERROR: provide --out or set SUPPLIERS_DB_PATH", file=sys.stderr)
        sys.exit(2)

    write_seed(Path(target), args.count, args.seed)


if __name__ == "__main__":
    main()
