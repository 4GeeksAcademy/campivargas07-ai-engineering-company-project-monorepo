"""Compatibility exports for TinyDB initialization.

Canonical database module lives in app/database.py.
"""

from app.database import db, suppliers_table

__all__ = ["db", "suppliers_table"]
