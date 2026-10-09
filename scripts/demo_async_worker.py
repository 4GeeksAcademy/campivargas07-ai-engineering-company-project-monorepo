"""Demo-only fault injection. Successful tasks execute the unchanged real flow.

The selected failure UUID executes a real PostgreSQL serialization error before
the flow, on each delivery. Never imported by the production worker entrypoint.
"""
from pathlib import Path

from sqlalchemy import text

from app.domains.tasks.repository import TaskRepository
from app.worker.celery_app import celery_app
import app.worker.inventory_health as task_module

real_flow = task_module.inventory_health_business_flow


def demo_flow(*, run_id):
    control = Path("/demo-control/failure-id")
    if control.exists() and control.read_text().strip() == run_id:
        with TaskRepository().engine.begin() as conn:
            conn.execute(text("DO $$ BEGIN RAISE EXCEPTION 'demo serialization failure' USING ERRCODE='40001'; END $$"))
    return real_flow(run_id=run_id)


if __name__ == "__main__":
    task_module.inventory_health_business_flow = demo_flow
    celery_app.worker_main(["worker", "--loglevel=INFO", "--concurrency=1", "--events"])
