"""
service.py — Telemetry Report Orchestration and Service Layer

Coordinates:
- Parameter validation and UTC window resolution (inclusive start, exclusive end).
- In-memory cache retrieval and caching (with (None, None) support).
- Invocation of pure analysis functions with identical time window.
- Assembly of typed TelemetryReportResponse.
- Zero credential exposure on database failures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import Session

from app.domains.telemetry.analysis import (
    get_api_latency_by_route,
    get_error_rate_by_type,
    get_events_per_day,
    get_login_failure_rate_per_day,
)
from app.domains.telemetry.cache import report_cache
from app.domains.telemetry.schemas import (
    ReportMetrics,
    ReportPeriod,
    TelemetryReportResponse,
)

logger = logging.getLogger("telemetry")


def resolve_report_window(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> tuple[datetime, datetime]:
    """
    Resolves and normalizes the time window [start_date, end_date) in UTC.

    Rules:
    - If end_date is omitted: defaults to current UTC time.
    - If start_date is omitted: defaults to 7 days before end_date.
    - Both timestamps are normalized to timezone-aware UTC.
    - Validates start_date < end_date. Raises ValueError if invalid.
    """
    if end_date is None:
        resolved_end = datetime.now(timezone.utc)
    elif end_date.tzinfo is None:
        resolved_end = end_date.replace(tzinfo=timezone.utc)
    else:
        resolved_end = end_date.astimezone(timezone.utc)

    if start_date is None:
        resolved_start = resolved_end - timedelta(days=7)
    elif start_date.tzinfo is None:
        resolved_start = start_date.replace(tzinfo=timezone.utc)
    else:
        resolved_start = start_date.astimezone(timezone.utc)

    if resolved_start >= resolved_end:
        raise ValueError("start_date must be strictly earlier than end_date")

    return resolved_start, resolved_end


def generate_telemetry_report(
    session: Session,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> TelemetryReportResponse:
    """
    Orchestrates report generation:
    1. Checks in-memory cache using raw request inputs (None, None handled as a unit).
    2. Resolves and normalizes UTC window once.
    3. Runs analysis pipeline across all 4 metrics.
    4. Caches and returns the full typed response.
    """
    raw_start_key = start_date.isoformat() if start_date is not None else None
    raw_end_key = end_date.isoformat() if end_date is not None else None

    # 1. Cache hit check
    cached = report_cache.get(raw_start_key, raw_end_key)
    if cached is not None:
        logger.info(
            "Telemetry report cache hit for window key: start=%s, end=%s",
            raw_start_key,
            raw_end_key,
        )
        return cached

    # 2. Window resolution
    resolved_start, resolved_end = resolve_report_window(start_date, end_date)

    # 3. Pure metrics calculation
    try:
        events_per_day = get_events_per_day(session, resolved_start, resolved_end)
        error_rate_by_type = get_error_rate_by_type(session, resolved_start, resolved_end)
        login_failure_rate_per_day = get_login_failure_rate_per_day(session, resolved_start, resolved_end)
        api_latency_by_route = get_api_latency_by_route(session, resolved_start, resolved_end)
    except Exception as exc:
        logger.error(
            "Database failure while computing telemetry report: %s",
            exc.__class__.__name__,
        )
        raise

    # 4. Assembly of response
    response = TelemetryReportResponse(
        period=ReportPeriod(
            from_=resolved_start,
            to=resolved_end,
        ),
        metrics=ReportMetrics(
            events_per_day=events_per_day,
            error_rate_by_type=error_rate_by_type,
            login_failure_rate_per_day=login_failure_rate_per_day,
            api_latency_by_route=api_latency_by_route,
        ),
    )

    # 5. Store in cache
    report_cache.set(raw_start_key, raw_end_key, response)
    logger.info(
        "Telemetry report generated and cached: start=%s, end=%s, events_days=%d",
        resolved_start.isoformat(),
        resolved_end.isoformat(),
        len(events_per_day),
    )

    return response

