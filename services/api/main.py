"""Compatibility entrypoint for delivery structure.

Keeps canonical app implementation under app/main.py while exposing
services/api/main.py as requested by the rubric.
"""

from app.main import app

__all__ = ["app"]
