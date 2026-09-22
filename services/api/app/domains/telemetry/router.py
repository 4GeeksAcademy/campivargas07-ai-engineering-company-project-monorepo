"""
router.py — Brasaland · Telemetry HTTP API Endpoints

Prefix: /telemetry
Endpoints:
- POST /telemetry/events — Ingests telemetry event batches, validates each event individually,
                           and performs an idempotent bulk insert into PostgreSQL (telemetry_events).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import TypeAdapter, ValidationError
from sqlmodel import Session

from app.database import get_db
from app.domains.telemetry.mapping import telemetry_event_to_row
from app.domains.telemetry.repository import bulk_insert_telemetry_events
from app.domains.telemetry.schemas import (
    TelemetryBatchRequest,
    TelemetryBatchResponse,
    TelemetryEvent,
)

logger = logging.getLogger("telemetry")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Read TELEMETRY_ENDPOINT from environment for future persistence routing
TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "")

# Module-level TypeAdapter for validated discriminated union
TELEMETRY_EVENT_ADAPTER: TypeAdapter[TelemetryEvent] = TypeAdapter(TelemetryEvent)


@router.post(
    "/events",
    status_code=status.HTTP_200_OK,
    response_model=TelemetryBatchResponse,
    summary="Receive a batch of telemetry events",
    description="Validates each telemetry event individually and stores valid events in PostgreSQL in a single bulk insert.",
)
def receive_telemetry_events(
    batch: TelemetryBatchRequest,
    session: Session = Depends(get_db),
) -> TelemetryBatchResponse:
    """Accepts a batch of up to 20 telemetry events.

    - Validates each raw event individually with TypeAdapter(TelemetryEvent).
    - Unparseable/invalid events increment rejected without failing the whole batch.
    - Valid events are mapped to the 8-column schema and stored via a single bulk insert.
    - Idempotent duplicate handling via ON CONFLICT (event_id) DO NOTHING.
    - Returns counters: received = stored + rejected.
    """
    total_received = len(batch.events)
    if total_received == 0:
        logger.info("Received telemetry batch: count=0, event_types=[]")
        return TelemetryBatchResponse(received=0, stored=0, rejected=0)

    valid_rows: list[dict[str, Any]] = []
    rejected_validation = 0
    valid_event_types: list[str] = []

    for index, raw_event in enumerate(batch.events):
        try:
            validated_event = TELEMETRY_EVENT_ADAPTER.validate_python(raw_event)
            row = telemetry_event_to_row(validated_event)
            valid_rows.append(row)
            valid_event_types.append(validated_event.event_type)
        except ValidationError as err:
            rejected_validation += 1
            event_type_hint = (
                raw_event.get("event_type", "unknown")
                if isinstance(raw_event, dict)
                else "non_dict"
            )
            logger.warning(
                "Invalid telemetry event rejected: index=%d, event_type=%s, errors_count=%d",
                index,
                event_type_hint,
                len(err.errors()),
            )

    logger.info("Received telemetry batch: count=%d, event_types=%s", total_received, valid_event_types)

    stored_count = 0
    if valid_rows:
        try:
            stored_count = bulk_insert_telemetry_events(session, valid_rows)
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Database failure while storing telemetry batch: %s", exc.__class__.__name__)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service temporarily unavailable",
            ) from exc

    # Duplicates among valid events were not stored
    duplicates_count = len(valid_rows) - stored_count
    total_rejected = rejected_validation + duplicates_count

    logger.info(
        "Processed telemetry batch: received=%d, stored=%d, rejected=%d (invalid=%d, duplicates=%d)",
        total_received,
        stored_count,
        total_rejected,
        rejected_validation,
        duplicates_count,
    )

    return TelemetryBatchResponse(
        received=total_received,
        stored=stored_count,
        rejected=total_rejected,
    )
