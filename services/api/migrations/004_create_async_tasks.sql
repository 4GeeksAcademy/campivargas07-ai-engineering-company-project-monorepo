-- Tracking uses the flow UUID directly; there is no mapping table or job_runs reuse.
CREATE TABLE IF NOT EXISTS async_tasks (
    task_id UUID PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    attempt INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    result JSON
);
CREATE TABLE IF NOT EXISTS task_dead_letters (
    task_id UUID PRIMARY KEY REFERENCES async_tasks(task_id),
    attempt INTEGER NOT NULL,
    error VARCHAR(200) NOT NULL,
    failed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
