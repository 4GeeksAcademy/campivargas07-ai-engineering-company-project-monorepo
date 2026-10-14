from functools import lru_cache
import os
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlmodel import Session

from .models import AsyncTaskRecord, TaskDeadLetter, utcnow


class AttemptsExhausted(Exception):
    """A redelivery cannot execute the business flow a fifth time."""


@lru_cache(maxsize=4)
def _engine(url: str):
    return create_engine(url, pool_pre_ping=True)


class TaskRepository:
    def __init__(self, engine=None):
        self.engine = engine if engine is not None else _engine(os.environ["DATABASE_URL"])

    def register(self, task_id: str) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            session.add(AsyncTaskRecord(task_id=UUID(task_id)))
            session.commit()

    def get(self, task_id: str) -> AsyncTaskRecord | None:
        with Session(self.engine, expire_on_commit=False) as session:
            return session.get(AsyncTaskRecord, UUID(task_id))

    def started(self, task_id: str, attempt: int) -> AsyncTaskRecord:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(AsyncTaskRecord, UUID(task_id), with_for_update=True)
            if row is None:
                raise ValueError("Unknown task")
            if row.status not in {"SUCCESS", "FAILURE"}:
                if row.attempt >= 4:
                    raise AttemptsExhausted()
                row.status = "STARTED"
                row.started_at = utcnow()
                row.attempt = max(row.attempt + 1, attempt)
                session.add(row)
                # record_execution_start uses ON CONFLICT DO NOTHING, so explicitly
                # transition the previously scheduled run without altering the pipeline.
                self._pipeline_state(session, task_id, "RUNNING")
                session.commit()
            return row

    def retrying(self, task_id: str) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(AsyncTaskRecord, UUID(task_id), with_for_update=True)
            row.status = "RETRY"
            session.add(row)
            self._pipeline_state(session, task_id, "SCHEDULED")
            session.commit()

    def succeeded(self, task_id: str, result: dict) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(AsyncTaskRecord, UUID(task_id), with_for_update=True)
            row.status = "SUCCESS"
            row.result = result
            row.completed_at = utcnow()
            session.add(row)
            # SKIPPED remains an explicit pipeline result, not a Celery failure.
            self._pipeline_state(session, task_id, result["status"], completed=True)
            session.commit()

    def failed(self, task_id: str, error: str, attempt: int, *, dead_letter: bool = True) -> None:
        with Session(self.engine, expire_on_commit=False) as session:
            row = session.get(AsyncTaskRecord, UUID(task_id), with_for_update=True)
            if row is not None and row.status in {"SUCCESS", "FAILURE"}:
                return
            if row is not None:
                row.status = "FAILURE"
                row.attempt = max(row.attempt, attempt)
                row.result = {"error": error}
                row.completed_at = utcnow()
                session.add(row)
                if dead_letter and session.get(TaskDeadLetter, UUID(task_id)) is None:
                    session.add(TaskDeadLetter(task_id=UUID(task_id), attempt=row.attempt, error=error))
            self._pipeline_state(session, task_id, "FAILED", completed=True, error=error)
            session.commit()

    def _pipeline_state(self, session, task_id, status, *, completed=False, error=None):
        # Reporting is PostgreSQL-only; unit-test tracking also supports SQLite.
        if self.engine.dialect.name == "postgresql":
            session.execute(text(
                "UPDATE reporting.pipeline_execution_logs SET pipeline_run_status=:status, "
                "completed_at=:completed_at, error_detail=:error WHERE pipeline_run_id=:id"
            ), {"status": status, "completed_at": utcnow() if completed else None,
                "error": error, "id": UUID(task_id)})
