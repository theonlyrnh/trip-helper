"""Jobs table as the durable source of task state."""

from __future__ import annotations

import logging

from celery.result import AsyncResult
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.infrastructure.db.models import Job


logger = logging.getLogger(__name__)

TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED"})
ACTIVE_STATES = frozenset({"PENDING", "QUEUED", "RUNNING", "RETRYING"})


def create_job(
    db: Session,
    *,
    owner_id: str,
    kind: str,
    trip_id: str | None = None,
    document_id: str | None = None,
    queue: str = "cpu",
    idempotency_key: str | None = None,
    result_ref: str | None = None,
) -> Job:
    if idempotency_key:
        existing = db.scalar(
            select(Job).where(Job.owner_id == owner_id, Job.idempotency_key == idempotency_key)
        )
        if existing:
            return existing
    job = Job(
        owner_id=owner_id,
        kind=kind,
        trip_id=trip_id,
        document_id=document_id,
        queue=queue,
        idempotency_key=idempotency_key,
        result_ref=result_ref,
        state="PENDING",
    )
    db.add(job)
    db.flush()
    return job


def dispatch_job(db: Session, job: Job) -> Job:
    """Publish after metadata is committed so a worker can always find the job."""
    from app.workers.tasks import execute_job

    if job.state in {"QUEUED", "RUNNING", "SUCCEEDED"}:
        return job
    job.state = "QUEUED"
    job.message = "任务已排队"
    db.commit()
    try:
        result = execute_job.apply_async(args=[job.id], queue=job.queue)
        job.celery_task_id = result.id
        db.commit()
    except Exception as exc:
        # Preserve the durable job row and make a transient broker outage visible.
        job.state = "RETRYING"
        job.error_code = "QUEUE_UNAVAILABLE"
        job.error_message = "任务队列暂不可用，稍后可重试"
        db.commit()
        logger.warning("Unable to publish job", extra={"job_id": job.id, "event": "queue_publish_failed"})
    db.refresh(job)
    return job


def cancel_job(db: Session, job: Job) -> Job:
    from datetime import UTC, datetime

    if job.state in TERMINAL_STATES:
        return job
    if job.celery_task_id:
        AsyncResult(job.celery_task_id).revoke(terminate=False)
    result = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.state.in_(ACTIVE_STATES))
        .values(state="CANCELLED", cancelled_at=datetime.now(UTC), message="任务已取消")
    )
    if result.rowcount == 0:
        db.refresh(job)
        return job
    db.commit()
    db.refresh(job)
    return job


def retry_job(db: Session, job: Job) -> Job:
    if job.state not in {"FAILED", "RETRYING", "CANCELLED"}:
        return job
    job.state = "PENDING"
    job.error_code = None
    job.error_message = None
    job.message = "等待重试"
    return dispatch_job(db, job)


def conditional_terminal_update(
    db: Session,
    job: Job,
    *,
    state: str,
    attempt: int,
    message: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Commit a worker result only if it still owns the current attempt."""
    from datetime import UTC, datetime

    values: dict[str, object] = {
        "state": state,
        "message": message,
        "finished_at": datetime.now(UTC),
        "error_code": error_code,
        "error_message": error_message,
    }
    if state == "SUCCEEDED":
        values["progress"] = 100
    result = db.execute(
        update(Job)
        .where(Job.id == job.id, Job.state == "RUNNING", Job.attempt == attempt)
        .values(**values)
    )
    return result.rowcount == 1
