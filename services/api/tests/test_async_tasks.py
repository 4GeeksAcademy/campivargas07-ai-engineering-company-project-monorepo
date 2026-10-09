"""Queue boundary, durable state, retry policy and dead letters (isolated DB)."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from billiard.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
from celery.exceptions import Retry
from fastapi import HTTPException
from kombu.exceptions import OperationalError as BrokerError
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, select

from app.domains.reporting.repository import ReportingRepository
from app.domains.reporting.router import get_reporting_service
from app.domains.reporting.service import ReportingService
from app.domains.tasks.models import AsyncTaskRecord, TaskDeadLetter
from app.domains.tasks.repository import TaskRepository
from app.domains.tasks.router import get_task_repository
from app.main import app
from app.worker.celery_app import celery_app
from app.worker.inventory_health import run_inventory_health, TaskExecutionError, is_transient
import app.domains.reporting.service as reporting
import app.domains.tasks.router as task_router
import app.worker.inventory_health as worker


@pytest.fixture
def task_repo(sqlite_engine, monkeypatch):
    repo = TaskRepository(sqlite_engine)
    app.dependency_overrides[get_task_repository] = lambda: repo
    service = ReportingService(ReportingRepository(sqlite_engine))
    app.dependency_overrides[get_reporting_service] = lambda: service
    monkeypatch.setattr(worker, "TaskRepository", lambda: repo)
    yield repo
    app.dependency_overrides.pop(get_task_repository, None)
    app.dependency_overrides.pop(get_reporting_service, None)


def scheduled(monkeypatch):
    task_id = str(uuid4())
    monkeypatch.setattr(reporting, "trigger_inventory_health_flow", lambda **kw: {
        "flow_run_id": task_id, "status": "SCHEDULED", "enqueued_at": datetime.now(timezone.utc).isoformat(),
        "triggered_by": kw["triggered_by"], "message": "Inventory health business pipeline run enqueued successfully.",
    })
    return task_id


@pytest.mark.parametrize("role", ["admin", "manager"])
def test_immediate_publication_only_uuid(client, create_test_user, task_repo, monkeypatch, role):
    from app.domains.auth.service import create_access_token
    user = create_test_user(role=role)
    headers = {"Authorization": "Bearer " + create_access_token({"sub": str(user.doc_id)})}
    task_id = scheduled(monkeypatch)
    publications = []
    monkeypatch.setattr(run_inventory_health, "apply_async", lambda **kw: publications.append(kw))
    monkeypatch.setattr(worker, "inventory_health_business_flow", lambda **kw: pytest.fail("API executed the pipeline"))
    response = client.post("/reporting/inventory-health/runs", headers=headers)
    assert response.status_code == 202
    assert response.json()["task_id"] == response.json()["flow_run_id"] == task_id
    assert publications == [{"args": [task_id], "task_id": task_id, "retry": False}]
    assert task_repo.get(task_id).status == "PENDING"


@pytest.mark.parametrize("role", ["user", "employee"])
def test_trigger_permissions(client, create_test_user, task_repo, monkeypatch, role):
    from app.domains.auth.service import create_access_token
    user = create_test_user(role=role)
    headers = {"Authorization": "Bearer " + create_access_token({"sub": str(user.doc_id)})}
    monkeypatch.setattr(run_inventory_health, "apply_async", lambda **kw: pytest.fail("Unauthorized publication"))
    assert client.post("/reporting/inventory-health/runs", headers=headers).status_code == 403


def test_authentication_required(client, task_repo):
    assert client.post("/reporting/inventory-health/runs").status_code == 401
    assert client.get(f"/tasks/{uuid4()}").status_code == 401


def test_broker_down_is_503_and_failed(client, auth_headers, task_repo, monkeypatch):
    task_id = scheduled(monkeypatch)
    def fail(**kwargs):
        raise BrokerError("redis://secret:password@host:6379/0")
    monkeypatch.setattr(run_inventory_health, "apply_async", fail)
    service = ReportingService(ReportingRepository(task_repo.engine))
    with pytest.raises(HTTPException) as exc:
        service.trigger_run({"role": "admin", "uuid": str(uuid4())})
    assert exc.value.status_code == 503
    assert "password" not in exc.value.detail
    row = task_repo.get(task_id)
    assert row.status == "FAILURE"
    assert row.attempt == 0
    with Session(task_repo.engine) as session:
        assert session.get(TaskDeadLetter, uuid4()) is None
        assert session.exec(select(TaskDeadLetter)).all() == []


@pytest.mark.parametrize("state,status", [("PENDING", "pending"), ("RECEIVED", "pending"),
    ("RETRY", "pending"), ("STARTED", "started"), ("SUCCESS", "success"), ("FAILURE", "failure"), ("REVOKED", "failure")])
def test_task_state_mapping(client, auth_headers, task_repo, monkeypatch, state, status):
    task_id = str(uuid4())
    task_repo.register(task_id)
    monkeypatch.setattr(celery_app, "AsyncResult", lambda task_id: SimpleNamespace(state=state))
    response = client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"task_id": task_id, "status": status, "result": None}


def test_unknown_and_expired_are_not_pending(client, auth_headers, task_repo, monkeypatch):
    monkeypatch.setattr(celery_app, "AsyncResult", lambda task_id: SimpleNamespace(state="PENDING"))
    assert client.get(f"/tasks/{uuid4()}", headers=auth_headers).status_code == 404
    task_id = str(uuid4())
    task_repo.register(task_id)
    result = {"status": "COMPLETED", "flow_run_id": task_id}
    task_repo.succeeded(task_id, result)
    response = client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert response.json() == {"task_id": task_id, "status": "success", "result": result}
    with Session(task_repo.engine) as session:
        row = session.get(AsyncTaskRecord, UUID(task_id))
        row.completed_at = datetime.now(timezone.utc) - timedelta(days=2)
        session.add(row)
        session.commit()
    assert client.get(f"/tasks/{task_id}", headers=auth_headers).status_code == 410


def test_result_broker_unavailable(client, auth_headers, task_repo, monkeypatch):
    task_id = str(uuid4())
    task_repo.register(task_id)
    def unavailable(task_id):
        raise RedisConnectionError("private connection details")
    monkeypatch.setattr(celery_app, "AsyncResult", unavailable)
    response = client.get(f"/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 503
    assert "private" not in response.text


def execute(task_id, retries=0):
    run_inventory_health.push_request(id=task_id, retries=retries)
    try:
        return run_inventory_health.run(task_id)
    finally:
        run_inventory_health.pop_request()


def test_retries_exponential_then_durable_dlq(task_repo, monkeypatch, caplog):
    task_id = str(uuid4())
    task_repo.register(task_id)
    def transient(**kwargs):
        raise ConnectionError("postgresql://user:very-secret@host/db")
    monkeypatch.setattr(worker, "inventory_health_business_flow", transient)
    delays = []
    def retry(**kwargs):
        delays.append(kwargs["countdown"])
        raise Retry()
    monkeypatch.setattr(run_inventory_health, "retry", retry)
    for retries in range(3):
        with pytest.raises(Retry):
            execute(task_id, retries)
    assert delays == [5, 10, 20]
    with pytest.raises(TaskExecutionError):
        execute(task_id, 3)
    row = task_repo.get(task_id)
    assert row.status == "FAILURE" and row.attempt == 4
    with Session(task_repo.engine) as session:
        dlq = session.get(TaskDeadLetter, UUID(task_id))
        assert dlq.attempt == 4
        assert dlq.failed_at is not None
        assert "very-secret" not in dlq.error
    assert "very-secret" not in caplog.text
    # Callback/redelivery cannot create duplicate DLQ entries or reset failures.
    task_repo.failed(task_id, "ignored", 4)
    with Session(task_repo.engine) as session:
        assert len(session.exec(select(TaskDeadLetter)).all()) == 1


def test_nontransient_fails_without_retry(task_repo, monkeypatch):
    task_id = str(uuid4())
    task_repo.register(task_id)
    def permanent(**kwargs):
        raise ValueError("sensitive payload")
    monkeypatch.setattr(worker, "inventory_health_business_flow", permanent)
    monkeypatch.setattr(run_inventory_health, "retry", lambda **kw: pytest.fail("Permanent error retried"))
    with pytest.raises(TaskExecutionError, match="ValueError"):
        execute(task_id)
    with Session(task_repo.engine) as session:
        assert session.get(TaskDeadLetter, UUID(task_id)).attempt == 1


def test_success_redelivery_and_skipped_contract(task_repo, monkeypatch):
    task_id = str(uuid4())
    task_repo.register(task_id)
    calls = []
    result = {"flow_run_id": task_id, "status": "SKIPPED", "message": "Concurrency lock"}
    monkeypatch.setattr(worker, "inventory_health_business_flow", lambda **kw: calls.append(kw) or result)
    assert execute(task_id) == result
    assert execute(task_id) == result
    assert calls == [{"run_id": task_id}]
    assert task_repo.get(task_id).status == "SUCCESS"


@pytest.mark.parametrize("code,expected", [("08006", True), ("40001", True), ("40P01", True),
    ("55P03", True), ("57014", True), ("28P01", False), ("42P01", False)])
def test_transient_sqlstate_allowlist(code, expected):
    error = OperationalError("query", {}, SimpleNamespace(pgcode=code))
    assert is_transient(error) is expected


def test_soft_timeout_records_dlq_without_retry(task_repo, monkeypatch):
    task_id = str(uuid4())
    task_repo.register(task_id)
    def timeout(**kwargs):
        raise SoftTimeLimitExceeded()
    monkeypatch.setattr(worker, "inventory_health_business_flow", timeout)
    with pytest.raises(TaskExecutionError, match="Execution time limit"):
        execute(task_id)
    with Session(task_repo.engine) as session:
        assert session.get(TaskDeadLetter, UUID(task_id)).attempt == 1


def test_failure_callback_records_durable_failure(task_repo):
    task_id = str(uuid4())
    task_repo.register(task_id)
    task_repo.started(task_id, 1)
    run_inventory_health.push_request(id=task_id, retries=0)
    try:
        run_inventory_health.on_failure(TimeLimitExceeded(), task_id, [task_id], {}, None)
    finally:
        run_inventory_health.pop_request()
    assert task_repo.get(task_id).status == "FAILURE"
    with Session(task_repo.engine) as session:
        assert session.get(TaskDeadLetter, UUID(task_id)).error == "Execution time limit exceeded"


def test_hard_timeout_parent_persists_before_ack(task_repo, monkeypatch):
    from celery.worker.request import Request
    task_id = str(uuid4())
    task_repo.register(task_id)
    task_repo.started(task_id, 1)
    request = object.__new__(worker.InventoryRequest)
    request.id = task_id
    calls = []
    def parent_timeout(self, soft, timeout):
        assert task_repo.get(task_id).status == "FAILURE"
        calls.append((soft, timeout))
    monkeypatch.setattr(Request, "on_timeout", parent_timeout)
    request.on_timeout(False, 900)
    assert calls == [(False, 900)]
    with Session(task_repo.engine) as session:
        assert session.get(TaskDeadLetter, UUID(task_id)).attempt == 1


def test_retry_publication_failure_keeps_delivery(task_repo, monkeypatch):
    from celery.exceptions import Reject
    task_id = str(uuid4())
    task_repo.register(task_id)
    def transient(**kwargs):
        raise ConnectionError("transient database failure")
    def broker_down(**kwargs):
        raise Reject("private broker connection", requeue=False)
    monkeypatch.setattr(worker, "inventory_health_business_flow", transient)
    monkeypatch.setattr(run_inventory_health, "retry", broker_down)
    with pytest.raises(Reject) as exc:
        execute(task_id)
    assert exc.value.requeue is True
    assert "private" not in str(exc.value)
    assert task_repo.get(task_id).status == "RETRY"


def test_worker_logging_removes_credentials_and_sql_details():
    import logging
    from app.worker.logging import SafeWorkerLogs
    record = logging.LogRecord("celery", logging.INFO, "", 1,
                               "Connected to redis://user:secret@host/0", (), None)
    SafeWorkerLogs().filter(record)
    assert "secret" not in record.getMessage()
    record = logging.LogRecord("prefect", logging.ERROR, "", 1,
                               "SQL failed with confidential payload", (), (ValueError, ValueError("secret"), None))
    SafeWorkerLogs().filter(record)
    assert "confidential" not in record.getMessage()
    assert record.exc_info is None


def test_redelivery_after_four_started_attempts_does_not_run_fifth(task_repo, monkeypatch):
    task_id = str(uuid4())
    task_repo.register(task_id)
    for attempt in range(1, 5):
        task_repo.started(task_id, attempt)
    monkeypatch.setattr(worker, "inventory_health_business_flow", lambda **kw: pytest.fail("Fifth attempt executed"))
    with pytest.raises(TaskExecutionError, match="attempts exhausted"):
        execute(task_id, 3)
    with Session(task_repo.engine) as session:
        assert session.get(TaskDeadLetter, UUID(task_id)).attempt == 4
