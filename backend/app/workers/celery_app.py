"""Celery discovery entry point used by native systemd worker units."""

from app.infrastructure.queue.celery import celery_app

# Celery's command-line loader imports this module in a fresh process. Import
# the task module here so the registry is populated before worker boot.
from app.workers import tasks as _tasks  # noqa: F401,E402

__all__ = ["celery_app"]
