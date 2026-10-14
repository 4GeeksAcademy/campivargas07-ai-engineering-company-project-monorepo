import os

from celery import Celery
from app.worker import logging as safe_logging  # noqa: F401

RESULT_EXPIRES = 86400
celery_app = Celery("brasaland", include=["app.worker.inventory_health"])
celery_app.conf.update(
    broker_url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    result_backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_default_queue="inventory-health",
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_soft_time_limit=840,
    task_time_limit=900,
    worker_prefetch_multiplier=1,
    worker_send_task_events=True,
    task_send_sent_event=True,
    task_publish_retry=False,
    broker_connection_timeout=2,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 1800, "socket_connect_timeout": 2, "socket_timeout": 2},
    result_backend_transport_options={"visibility_timeout": 1800},
    visibility_timeout=1800,
    redis_socket_connect_timeout=2,
    redis_socket_timeout=2,
    result_expires=RESULT_EXPIRES,
)
