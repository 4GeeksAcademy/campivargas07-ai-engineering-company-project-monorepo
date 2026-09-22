"""
mapping.py — Pure mapping from validated Pydantic TelemetryEvent to database row dictionary.

Transforms canonical TelemetryEvent objects into the exact 8-column database schema:
- Converts camelCase aliases to snake_case column names.
- Serializes UUID and datetime preserving UTC timezone.
- Copies ONLY validated properties into tags (never full envelope, no extra properties).
- Assigns producer service authoritatively on the server.
- Leaves entity_action and schemaVersion out of persistent storage.
"""

from __future__ import annotations

from typing import Any

DEFAULT_SERVICE = "backoffice"


def telemetry_event_to_row(
    event: Any,
    service: str = DEFAULT_SERVICE,
) -> dict[str, Any]:
    """
    Pure mapping function converting a validated TelemetryEvent into an 8-column database row dictionary.

    Columns produced:
    1. event_id (UUID)
    2. event_type (str)
    3. timestamp (datetime)
    4. service (str)
    5. session_id (Optional[str])
    6. user_id (Optional[UUID])
    7. request_id (str)
    8. tags (dict, only validated properties)
    """
    # Extract only validated properties as pure JSON-serializable dictionary
    tags = event.properties.model_dump(mode="json")

    return {
        "event_id": event.eventId,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "service": service,
        "session_id": event.sessionId,
        "user_id": event.userId,
        "request_id": event.requestId,
        "tags": tags,
    }

