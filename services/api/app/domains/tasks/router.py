from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.domains.auth.dependencies import get_current_user
from app.worker.celery_app import RESULT_EXPIRES, celery_app
from .repository import TaskRepository

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskStatusResponse(BaseModel):
    task_id: str
    status: Literal["pending", "started", "success", "failure"]
    result: dict[str, Any] | None = None


def get_task_repository() -> TaskRepository:
    return TaskRepository()


@router.get("/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: UUID, current_user: dict = Depends(get_current_user),
                    repository: TaskRepository = Depends(get_task_repository)):
    task_id = str(task_id)
    try:
        record = repository.get(task_id)
        if record is None:
            raise HTTPException(404, "Task not found")
        if record.completed_at:
            completed_at = record.completed_at.replace(tzinfo=timezone.utc)
            if (datetime.now(timezone.utc) - completed_at).total_seconds() >= RESULT_EXPIRES:
                raise HTTPException(410, "Task result expired")
        state = celery_app.AsyncResult(task_id).state
    except (RedisError, SQLAlchemyError):
        raise HTTPException(503, "Task status temporarily unavailable") from None
    mapping = {"PENDING": "pending", "RECEIVED": "pending", "RETRY": "pending",
               "STARTED": "started", "SUCCESS": "success", "FAILURE": "failure", "REVOKED": "failure"}
    # PENDING alone cannot distinguish an unknown ID or missing backend key.
    # Persistent tracking supplies that distinction and survives Redis result loss.
    if record.status in {"SUCCESS", "FAILURE"}:
        state = record.status
    elif state == "PENDING":
        state = record.status
    status = mapping.get(state)
    if status is None:
        raise HTTPException(503, "Task state temporarily unavailable")
    return TaskStatusResponse(task_id=task_id, status=status,
                              result=record.result if status in {"success", "failure"} else None)
