import logging
import os
from fastapi import APIRouter, status

from app.domains.telemetry.schemas import TelemetryBatch, TelemetryBatchResponse

logger = logging.getLogger("telemetry")

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Read TELEMETRY_ENDPOINT from environment for future persistence routing
TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "")


@router.post(
    "/events",
    status_code=status.HTTP_200_OK,
    response_model=TelemetryBatchResponse,
    summary="Receive a batch of telemetry events",
    description="Validates and acknowledges telemetry event batches according to approved contracts. Does not persist data.",
)
def receive_telemetry_events(batch: TelemetryBatch) -> TelemetryBatchResponse:
    """Accepts a batch of up to 20 validated telemetry events.
    
    Logs event count and event types for zero-PII observability.
    Does not persist events to any database, file, or cache.
    """
    event_types = [event.event_type for event in batch.events]
    count = len(batch.events)

    logger.info("Received telemetry batch: count=%d, event_types=%s", count, event_types)

    return TelemetryBatchResponse(received=count)

