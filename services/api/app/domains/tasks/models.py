from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Column, DateTime, JSON
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AsyncTaskRecord(SQLModel, table=True):
    __tablename__ = "async_tasks"

    task_id: UUID = Field(primary_key=True)
    status: str = Field(default="PENDING", max_length=20)
    attempt: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    completed_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    result: dict | None = Field(default=None, sa_column=Column(JSON))


class TaskDeadLetter(SQLModel, table=True):
    __tablename__ = "task_dead_letters"

    # One terminal dead letter per task, including duplicate delivery callbacks.
    task_id: UUID = Field(primary_key=True, foreign_key="async_tasks.task_id")
    attempt: int
    error: str = Field(max_length=200)
    failed_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
