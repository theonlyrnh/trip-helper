"""Audit persistence that deliberately excludes secret and content payloads."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.infrastructure.db.models import AuditEvent


def record_audit(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    trace_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        trace_id=trace_id,
        metadata_json=metadata or None,
    )
    db.add(event)
    return event

