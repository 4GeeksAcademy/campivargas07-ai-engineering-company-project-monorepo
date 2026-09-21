"""models.py — Brasaland · Inventario (re-exporta modelos del catálogo)

Los modelos InventarioLocal y MovimientoInventario viven en
app/domains/ingredients/models.py porque comparten Base y FKs.
Este módulo los re-exporta para respetar la organización por dominios.
"""
from app.domains.ingredients.models import InventarioLocal, MovimientoInventario

__all__ = ["InventarioLocal", "MovimientoInventario"]