"""Celery configuration with explicit CPU and GPU queue routing."""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings


settings = get_settings()
celery_app = Celery("trip_helper", broker=settings.redis_url, backend=settings.celery_result_backend or settings.redis_url)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    include=["app.workers.tasks"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.tasks_eager or settings.celery_task_always_eager,
    task_routes={
        "app.workers.tasks.process_document": {"queue": "cpu"},
        "app.workers.tasks.recognize_document": {"queue": "gpu"},
        "app.workers.tasks.execute_job": {"queue": "cpu"},
    },
)
