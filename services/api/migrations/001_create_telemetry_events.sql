-- Migration 001: Create telemetry_events table
-- Version: 001
-- Description: Idempotent append-only telemetry events log table with exactly 8 columns and 3 indexes.

CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(100) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    service VARCHAR(50) NOT NULL,
    session_id VARCHAR(100),
    user_id UUID,
    request_id VARCHAR(100) NOT NULL,
    tags JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- Explicit indexes required for querying telemetry efficiently
CREATE INDEX IF NOT EXISTS idx_telemetry_events_timestamp ON telemetry_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_event_type ON telemetry_events (event_type);
CREATE INDEX IF NOT EXISTS idx_telemetry_events_tags_gin ON telemetry_events USING gin (tags);

