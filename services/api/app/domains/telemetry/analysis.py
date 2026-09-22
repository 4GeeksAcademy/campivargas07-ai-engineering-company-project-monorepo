"""
analysis.py — Brasaland · Pure Telemetry Analysis Metrics via Pandas

Implements the SQL -> Pandas DataFrame -> Normalization/Refinement -> GroupBy + Agg -> JSON-safe pipeline:
1. get_events_per_day: Daily volume of all events grouped by UTC date.
2. get_error_rate_by_type: Frequency and proportion of technical error events.
3. get_login_failure_rate_per_day: Daily failure percentage of authentication attempts.
4. get_api_latency_by_route: Request count, average, and P95 latency grouped by backend route.

Strict operational rules:
- Queries load ONLY required columns and filter strictly by [start_date, end_date) in SQL.
- When applicable, event_type is filtered in SQL (no client-side filtering of irrelevant types).
- Timestamps are explicitly converted to UTC with pd.to_datetime(..., utc=True).
- Deterministic ordering of records.
- All returned values are sanitized to native Python types (zero NaN, NaT, or NumPy types).
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlmodel import Session


def _parse_tags(val: Any) -> dict[str, Any]:
    """Safely extracts a dictionary from a tags value (JSON string or dict)."""
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def get_events_per_day(
    session: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Computes total event volume grouped by UTC date within [start_date, end_date).

    Answers: ¿Cuál es el volumen diario de eventos y en qué días cambia la actividad del sistema?
    Returns: [{"date": "YYYY-MM-DD", "event_count": N}]
    """
    stmt = text(
        "SELECT timestamp FROM telemetry_events "
        "WHERE timestamp >= :start_date AND timestamp < :end_date"
    )
    df = pd.read_sql(stmt, session.connection(), params={"start_date": start_date, "end_date": end_date})
    if df.empty or "timestamp" not in df.columns:
        return []

    # 2. Convert timestamp to UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    # 3. Discard invalid timestamps
    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return []

    # 4. Extract date dimension in UTC
    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")

    # 7. Groupby & 8. Aggregation
    grouped = df.groupby("date", as_index=False)["timestamp"].count()
    grouped.rename(columns={"timestamp": "event_count"}, inplace=True)

    # 9. Deterministic ordering & 10. reset_index()
    grouped = grouped.sort_values(by="date", ascending=True).reset_index(drop=True)

    # 11. Convert to records & 12. Sanitize to native JSON-safe Python types
    records = grouped.to_dict(orient="records")
    return [
        {
            "date": str(row["date"]),
            "event_count": int(row["event_count"]),
        }
        for row in records
    ]


def get_error_rate_by_type(
    session: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Computes count and proportion of technical errors by event type within [start_date, end_date).

    Answers: ¿Qué tipos de errores técnicos ocurren con mayor frecuencia y qué proporción representan entre todos los errores?
    Filters in SQL: 'form_validation_failed', 'system_exception_captured', 'external_integration_failed'
    Returns: [{"event_type": str, "error_count": int, "error_rate": float}]
    """
    stmt = text(
        "SELECT event_type FROM telemetry_events "
        "WHERE timestamp >= :start_date AND timestamp < :end_date "
        "AND event_type IN ('form_validation_failed', 'system_exception_captured', 'external_integration_failed')"
    )
    df = pd.read_sql(stmt, session.connection(), params={"start_date": start_date, "end_date": end_date})
    if df.empty or "event_type" not in df.columns:
        return []

    # 6. Discard rows without required event_type
    df = df.dropna(subset=["event_type"])
    total_errors = len(df)
    if total_errors == 0:
        return []

    # 7. Groupby & 8. Aggregation
    grouped = df.groupby("event_type", as_index=False).agg(error_count=("event_type", "count"))

    # Compute error_rate = error_count / total_errors * 100
    grouped["error_rate"] = ((grouped["error_count"] / total_errors) * 100.0).round(2)

    # 9. Deterministic ordering (highest count first, then alphabetical) & 10. reset_index()
    grouped = grouped.sort_values(
        by=["error_count", "event_type"],
        ascending=[False, True],
    ).reset_index(drop=True)

    # 11. Convert to records & 12. Sanitize
    records = grouped.to_dict(orient="records")
    return [
        {
            "event_type": str(row["event_type"]),
            "error_count": int(row["error_count"]),
            "error_rate": float(row["error_rate"]),
        }
        for row in records
    ]


def get_login_failure_rate_per_day(
    session: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Computes daily percentage of failed login attempts within [start_date, end_date).

    Answers: ¿Qué porcentaje de intentos de inicio de sesión falla diariamente?
    Uses canonical events: 'user_logged_in' (success) and 'user_login_failed' (failed).
    Returns: [{"date": str, "successful_logins": int, "failed_logins": int, "total_attempts": int, "login_failure_rate": float}]
    """
    stmt = text(
        "SELECT timestamp, event_type FROM telemetry_events "
        "WHERE timestamp >= :start_date AND timestamp < :end_date "
        "AND event_type IN ('user_logged_in', 'user_login_failed')"
    )
    df = pd.read_sql(stmt, session.connection(), params={"start_date": start_date, "end_date": end_date})
    if df.empty or "timestamp" not in df.columns or "event_type" not in df.columns:
        return []

    # 2. Convert timestamp to UTC
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    # 3. Discard invalid timestamps
    df = df.dropna(subset=["timestamp", "event_type"])
    if df.empty:
        return []

    # 4. Extract date dimension in UTC
    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")

    # Flag success and failure
    df["is_success"] = (df["event_type"] == "user_logged_in").astype(int)
    df["is_failed"] = (df["event_type"] == "user_login_failed").astype(int)

    # 7. Groupby & 8. Aggregation
    grouped = df.groupby("date", as_index=False).agg(
        successful_logins=("is_success", "sum"),
        failed_logins=("is_failed", "sum"),
    )

    grouped["total_attempts"] = grouped["successful_logins"] + grouped["failed_logins"]

    # Filter dates with at least 1 attempt
    grouped = grouped[grouped["total_attempts"] > 0].copy()
    if grouped.empty:
        return []

    # Calculate login_failure_rate = (failed_logins / total_attempts) * 100
    grouped["login_failure_rate"] = (
        (grouped["failed_logins"] / grouped["total_attempts"]) * 100.0
    ).round(2)

    # 9. Deterministic ordering & 10. reset_index()
    grouped = grouped.sort_values(by="date", ascending=True).reset_index(drop=True)

    # 11. Convert to records & 12. Sanitize
    records = grouped.to_dict(orient="records")
    return [
        {
            "date": str(row["date"]),
            "successful_logins": int(row["successful_logins"]),
            "failed_logins": int(row["failed_logins"]),
            "total_attempts": int(row["total_attempts"]),
            "login_failure_rate": float(row["login_failure_rate"]),
        }
        for row in records
    ]


def get_api_latency_by_route(
    session: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Computes request count, average duration, and P95 latency by route within [start_date, end_date).

    Answers: ¿Qué rutas del backend responden más lentamente y cuáles necesitan investigación?
    Filters in SQL: event_type = 'api_latency_recorded'
    Extracts route_path and duration_ms from tags JSONB.
    Returns: [{"route_path": str, "request_count": int, "average_duration_ms": float, "p95_duration_ms": float}]
    """
    stmt = text(
        "SELECT tags FROM telemetry_events "
        "WHERE timestamp >= :start_date AND timestamp < :end_date "
        "AND event_type = 'api_latency_recorded'"
    )
    df = pd.read_sql(stmt, session.connection(), params={"start_date": start_date, "end_date": end_date})
    if df.empty or "tags" not in df.columns:
        return []

    # 4. Extract required dimensions from tags
    parsed_tags = df["tags"].apply(_parse_tags)
    df["route_path"] = parsed_tags.apply(
        lambda t: t.get("route_path") if isinstance(t, dict) and isinstance(t.get("route_path"), str) else None
    )
    df["duration_ms"] = parsed_tags.apply(
        lambda t: t.get("duration_ms") if isinstance(t, dict) else None
    )

    # 5. Convert numeric values with safety
    df["duration_ms"] = pd.to_numeric(df["duration_ms"], errors="coerce")

    # 6. Discard rows without required dimensions or with empty route / invalid duration
    df = df.dropna(subset=["route_path", "duration_ms"])
    df = df[df["route_path"].str.strip() != ""].copy()
    df = df[df["duration_ms"] >= 0].copy()
    if df.empty:
        return []

    # 7. Groupby & 8. Aggregation
    grouped = df.groupby("route_path", as_index=False).agg(
        request_count=("duration_ms", "count"),
        average_duration_ms=("duration_ms", "mean"),
        p95_duration_ms=("duration_ms", lambda s: s.quantile(0.95)),
    )

    grouped["average_duration_ms"] = grouped["average_duration_ms"].round(2)
    grouped["p95_duration_ms"] = grouped["p95_duration_ms"].round(2)

    # 9. Deterministic ordering: highest P95 first, then alphabetical by route
    grouped = grouped.sort_values(
        by=["p95_duration_ms", "route_path"],
        ascending=[False, True],
    ).reset_index(drop=True)

    # 11. Convert to records & 12. Sanitize
    records = grouped.to_dict(orient="records")
    return [
        {
            "route_path": str(row["route_path"]),
            "request_count": int(row["request_count"]),
            "average_duration_ms": float(row["average_duration_ms"]),
            "p95_duration_ms": float(row["p95_duration_ms"]),
        }
        for row in records
    ]

