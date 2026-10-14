import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from billiard.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from celery import Task
from celery.exceptions import Reject
from celery.worker.request import Request
from sqlalchemy.exc import DBAPIError, TimeoutError as PoolTimeout

from app.domains.tasks.repository import AttemptsExhausted, TaskRepository
from app.worker.celery_app import celery_app
from data.pipelines.inventory_health.flow import inventory_health_business_flow

logger = logging.getLogger("brasaland.tasks")


class TaskExecutionError(Exception):
    """Safe error suitable for Celery results, events and logs."""


def safe_error(exc: BaseException) -> str:
    # Do not retain arbitrary exception text, SQL parameters, URLs or payloads.
    if isinstance(exc, (SoftTimeLimitExceeded, TimeLimitExceeded)):
        return "Execution time limit exceeded"
    return f"{type(exc).__name__}: inventory health task failed"


def is_transient(exc: BaseException) -> bool:
    if isinstance(exc, (ConnectionError, TimeoutError, PoolTimeout)):
        return True
    if isinstance(exc, DBAPIError):
        code = getattr(exc.orig, "pgcode", None)
        if code:
            return code.startswith("08") or code in {"40001", "40P01", "55P03", "57014"}
        # Connectivity failures have no SQLSTATE; authentication/programming
        # errors with a SQLSTATE are deliberately not retried.
        from sqlalchemy.exc import OperationalError
        return exc.connection_invalidated or isinstance(exc, OperationalError)
    return False


class InventoryRequest(Request):
    def on_timeout(self, soft, timeout):
        # Hard timeouts run in the parent process, outside Task.on_failure.
        if not soft:
            try:
                repo = TaskRepository()
                row = repo.get(self.id)
                if row is not None:
                    repo.failed(self.id, "Execution time limit exceeded", row.attempt)
            except DBAPIError:
                self.reject(requeue=True)
                return
        super().on_timeout(soft, timeout)


class InventoryTask(Task):
    Request = InventoryRequest

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Ordinary failures are handled in the child; hard limits use Request.
        repo = TaskRepository()
        row = repo.get(task_id)
        if row is not None:
            repo.failed(task_id, safe_error(exc), max(row.attempt, self.request.retries + 1))
        duration = round((datetime.now(timezone.utc) - row.started_at.replace(tzinfo=timezone.utc)).total_seconds(), 3) if row and row.started_at else 0
        logger.error("task_id=%s attempt=%s status=failure duration_seconds=%s",
                     task_id, row.attempt if row else 0, duration)


@celery_app.task(bind=True, base=InventoryTask, name="brasaland.inventory_health", max_retries=3,
                 throws=(TaskExecutionError,))
def run_inventory_health(self, flow_run_id: str) -> dict:
    task_id = str(UUID(flow_run_id))
    if self.request.id != task_id:
        raise TaskExecutionError("Task and flow identifiers must match")
    repo = TaskRepository()
    started = time.monotonic()
    attempt = self.request.retries + 1
    try:
        row = repo.started(task_id, attempt)
    except AttemptsExhausted:
        try:
            repo.failed(task_id, "Execution attempts exhausted", 4)
        except DBAPIError:
            raise Reject("Durable task storage unavailable", requeue=True) from None
        raise TaskExecutionError("Execution attempts exhausted") from None
    except DBAPIError:
        raise Reject("Durable task storage unavailable", requeue=True) from None
    attempt = row.attempt
    try:
        if row.status == "SUCCESS":
            return row.result  # ACK redelivery without rerunning completed work.
        if row.status == "FAILURE":
            raise TaskExecutionError("Task already failed")
        logger.info("task_id=%s attempt=%s status=started duration_seconds=0", task_id, attempt)
        # All business logic stays in the original Prefect flow. Only the UUID
        # crosses Redis; database configuration and inputs are recovered here.
        result = inventory_health_business_flow(run_id=task_id)
        repo.succeeded(task_id, result)
    except TaskExecutionError:
        raise
    except Exception as exc:
        error = safe_error(exc)
        elapsed = round(time.monotonic() - started, 3)
        if is_transient(exc) and attempt <= self.max_retries:
            countdown = 5 * (2 ** (attempt - 1))
            try:
                repo.retrying(task_id)
            except DBAPIError:
                raise Reject("Durable task storage unavailable", requeue=True) from None
            logger.warning("task_id=%s attempt=%s status=retry duration_seconds=%s retry_in_seconds=%s error=%s",
                           task_id, attempt, elapsed, countdown, error)
            try:
                raise self.retry(exc=TaskExecutionError(error), countdown=countdown) from None
            except Reject:
                # Celery normally drops a delivery when publishing its retry
                # fails. Retain this UUID-only delivery for broker recovery.
                raise Reject("Retry publication unavailable", requeue=True) from None
        try:
            repo.failed(task_id, error, attempt)
        except DBAPIError:
            # Keep the delivery unacknowledged when durable DLQ storage is down.
            # Redelivery after recovery persists the failure before ACK.
            raise Reject("Durable task storage unavailable", requeue=True) from None
        logger.error("task_id=%s attempt=%s status=failure duration_seconds=%s error=%s",
                     task_id, attempt, elapsed, error)
        raise TaskExecutionError(error) from None
    logger.info("task_id=%s attempt=%s status=success duration_seconds=%s",
                task_id, attempt, round(time.monotonic() - started, 3))
    return result
