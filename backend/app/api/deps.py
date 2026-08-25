"""Authentication, CSRF, and ownership dependencies."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import secure_equals, token_digest
from app.infrastructure.db.models import Document, Export, Job, Trip, User, UserSession
from app.infrastructure.db.session import get_db


def _is_expired(value: datetime) -> bool:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value <= datetime.now(UTC)


def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
) -> UserSession:
    settings = get_settings()
    raw_token = request.cookies.get(settings.cookie_name)
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    session = db.scalar(select(UserSession).where(UserSession.token_hash == token_digest(raw_token)))
    if not session or _is_expired(session.expires_at):
        if session:
            db.delete(session)
            db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    request.state.user_session = session
    session.last_seen_at = datetime.now(UTC)
    return session


def get_current_user(
    db: Session = Depends(get_db),
    user_session: UserSession = Depends(get_current_session),
) -> User:
    user = db.get(User, user_session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator permission required")
    return user


def require_csrf(
    request: Request,
    user_session: UserSession = Depends(get_current_session),
) -> None:
    csrf_value = request.headers.get(get_settings().csrf_header_name)
    if not csrf_value or not secure_equals(csrf_value, user_session.csrf_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")


def get_owned_trip(trip_id: str, db: Session, user: User) -> Trip:
    trip = db.scalar(select(Trip).where(Trip.id == trip_id, Trip.owner_id == user.id))
    if not trip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trip not found")
    return trip


def get_owned_document(document_id: str, db: Session, user: User) -> Document:
    document = db.scalar(
        select(Document).join(Trip, Document.trip_id == Trip.id).where(Document.id == document_id, Trip.owner_id == user.id)
    )
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def get_owned_job(job_id: str, db: Session, user: User) -> Job:
    job = db.scalar(select(Job).where(Job.id == job_id, Job.owner_id == user.id))
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def get_owned_export(export_id: str, db: Session, user: User) -> Export:
    export = db.scalar(select(Export).where(Export.id == export_id, Export.owner_id == user.id))
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    return export
