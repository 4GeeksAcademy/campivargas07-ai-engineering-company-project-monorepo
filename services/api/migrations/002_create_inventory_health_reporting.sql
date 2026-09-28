-- Migration 002: Create Inventory Health Reporting Schema and Tables
-- Version: 002
-- Description: Idempotent DDL for reporting schema, inventory health snapshot, checkpoints, lineage, quarantine, and execution logs.

-- 1. Create reporting schema
CREATE SCHEMA IF NOT EXISTS reporting;

-- 2. Primary snapshot table
CREATE TABLE IF NOT EXISTS reporting.inventory_health_snapshot (
    snapshot_date DATE NOT NULL,
    local_id VARCHAR(50) NOT NULL,
    ingredient_id UUID NOT NULL,
    ingredient_sku VARCHAR(50) NOT NULL,
    ingredient_name VARCHAR(150) NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit_of_measure VARCHAR(30) NOT NULL,
    current_stock NUMERIC(10, 2) NOT NULL,
    minimum_stock NUMERIC(10, 2) NOT NULL,
    stock_level_ratio NUMERIC(10, 4),
    stock_deficit NUMERIC(10, 2) NOT NULL,
    is_stockout BOOLEAN NOT NULL,
    is_below_minimum BOOLEAN NOT NULL,
    inbound_quantity NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    outbound_quantity NUMERIC(10, 2) NOT NULL DEFAULT 0.0,
    insufficient_stock_attempts_count INTEGER NOT NULL DEFAULT 0,
    source_event_count INTEGER NOT NULL DEFAULT 0,
    source_first_event_at TIMESTAMPTZ,
    source_last_event_at TIMESTAMPTZ,
    pipeline_run_id UUID NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (snapshot_date, local_id, ingredient_id)
);

CREATE INDEX IF NOT EXISTS idx_reporting_snapshot_date ON reporting.inventory_health_snapshot (snapshot_date);
CREATE INDEX IF NOT EXISTS idx_reporting_snapshot_local ON reporting.inventory_health_snapshot (local_id);
CREATE INDEX IF NOT EXISTS idx_reporting_snapshot_ingredient ON reporting.inventory_health_snapshot (ingredient_id);
CREATE INDEX IF NOT EXISTS idx_reporting_snapshot_critical ON reporting.inventory_health_snapshot (is_stockout, is_below_minimum);

-- 3. Pipeline checkpoints table
CREATE TABLE IF NOT EXISTS reporting.pipeline_checkpoints (
    pipeline_name VARCHAR(100) NOT NULL,
    source_name VARCHAR(100) NOT NULL,
    watermark_timestamp TIMESTAMPTZ NOT NULL,
    watermark_event_id UUID NOT NULL,
    last_successful_run_id UUID NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (pipeline_name, source_name)
);

-- 4. Lineage table
CREATE TABLE IF NOT EXISTS reporting.inventory_health_lineage (
    pipeline_run_id UUID NOT NULL,
    event_id UUID NOT NULL,
    snapshot_date DATE NOT NULL,
    local_id VARCHAR(50) NOT NULL,
    ingredient_id UUID NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (pipeline_run_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_reporting_lineage_snapshot ON reporting.inventory_health_lineage (snapshot_date, local_id, ingredient_id);

-- 5. Quarantine table
CREATE TABLE IF NOT EXISTS reporting.inventory_health_quarantine (
    quarantine_id UUID PRIMARY KEY,
    event_id UUID,
    pipeline_run_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    reason_detail TEXT NOT NULL,
    raw_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    quarantined_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reporting_quarantine_run ON reporting.inventory_health_quarantine (pipeline_run_id);
CREATE INDEX IF NOT EXISTS idx_reporting_quarantine_event ON reporting.inventory_health_quarantine (event_id);

-- 6. Execution logs table
CREATE TABLE IF NOT EXISTS reporting.pipeline_execution_logs (
    pipeline_run_id UUID PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    pipeline_run_status VARCHAR(30) NOT NULL,
    watermark_timestamp TIMESTAMPTZ,
    source_events_read INTEGER NOT NULL DEFAULT 0,
    records_quarantined INTEGER NOT NULL DEFAULT 0,
    error_detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_reporting_execution_logs_started ON reporting.pipeline_execution_logs (started_at DESC);
