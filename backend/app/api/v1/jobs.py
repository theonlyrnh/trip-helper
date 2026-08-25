"""Task state inspection, cancellation, retry, and lightweight SSE status events."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_job, require_csrf
from app.infrastructure.db.models import Job, User
from app.infrastructure.db.session import get_db, get_session_factory
from app.schemas import JobRead
from app.services.jobs import cancel_job, retry_job


router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    return JobRead.model_validate(get_owned_job(job_id, db, user))


@router.post("/{job_id}/cancel", response_model=JobRead, dependencies=[Depends(require_csrf)])
def cancel(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    return JobRead.model_validate(cancel_job(db, get_owned_job(job_id, db, user)))


@router.post("/{job_id}/retry", response_model=JobRead, dependencies=[Depends(require_csrf)])
def retry(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> JobRead:
    return JobRead.model_validate(retry_job(db, get_owned_job(job_id, db, user)))


@router.get("/{job_id}/events")
async def events(job_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    # Verify ownership before opening an event stream. Each poll uses a new session.
    get_owned_job(job_id, db, user)

    async def stream():
        previous: str | None = None
        for _ in range(60):
            if await request.is_disconnected():
                return
            session = get_session_factory()()
            try:
                job = session.get(Job, job_id)
                if not job:
                    return
                payload = JobRead.model_validate(job).model_dump(mode="json")
                encoded = json.dumps(payload, ensure_ascii=False)
                if encoded != previous:
                    yield f"event: status\ndata: {encoded}\n\n"
                    previous = encoded
                if job.state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                    return
            finally:
                session.close()
            await asyncio.sleep(1)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

