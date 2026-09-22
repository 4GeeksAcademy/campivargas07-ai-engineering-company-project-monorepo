"""
repository.py — Data access layer for telemetry persistence.

Performs a single atomic bulk insert operation for validated telemetry events,
with idempotent duplicate handling via ON CONFLICT (event_id) DO NOTHING RETURNING.
Strictly append-only: zero update or delete capabilities.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlmodel import Session

from app.domains.telemetry.models import TelemetryEventRecord

logger = logging.getLogger("telemetry")


def bulk_insert_telemetry_events(
    session: Session,
    rows: list[dict[str, Any]],
) -> int:
    """
    Persists valid telemetry event rows in a single bulk INSERT operation.

    Guarantees:
    - If rows is empty, returns 0 without issuing any database queries.
    - Exactly ONE insert statement for the entire batch (no per-row queries or loops).
    - Idempotency via ON CONFLICT (event_id) DO NOTHING.
    - Returns the count of rows actually inserted (via RETURNING event_id).
    - Session commit/rollback is managed by the caller/transaction coordinator.
    """
    if not rows:
        return 0

    table = TelemetryEventRecord.__table__
    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else "postgresql"

    if dialect_name == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

    stmt = (
        dialect_insert(table)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["event_id"])
        .returning(table.c.event_id)
    )

    result = session.execute(stmt)
    inserted_rows = result.fetchall()
    return len(inserted_rows)

