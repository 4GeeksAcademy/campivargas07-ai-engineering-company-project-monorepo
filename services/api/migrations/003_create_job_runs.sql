-- Migration 003: Create job_runs table
-- Version: 003
-- Description: Table for background and nightly job orchestration runs with atomic claiming support.

CREATE TABLE IF NOT EXISTS job_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_name VARCHAR(100) NOT NULL,
    target_date DATE NOT NULL,
    status VARCHAR(30) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Index for searching and filtering by job_name and target_date
CREATE INDEX IF NOT EXISTS idx_job_runs_job_target ON job_runs (job_name, target_date);

-- Partial unique index ensuring that at most one execution is in 'processing' state
-- for any given (job_name, target_date) at any time.
CREATE UNIQUE INDEX IF NOT EXISTS uq_job_runs_processing ON job_runs (job_name, target_date) WHERE status = 'processing';
