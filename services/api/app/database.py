"""
database.py — Brasaland · TinyDB initialization

Centralized database access for all domains.
The DB file is located next to this module for predictability across CWDs.
"""

from __future__ import annotations

import os
from pathlib import Path

from tinydb import TinyDB

_default_path = Path(__file__).resolve().parent.parent.parent / "data" / "suppliers.json"
_db_path = Path(os.environ.get("SUPPLIERS_DB_PATH", str(_default_path)))
_db_path.parent.mkdir(parents=True, exist_ok=True)

db = TinyDB(_db_path)

suppliers_table = db.table("suppliers")
