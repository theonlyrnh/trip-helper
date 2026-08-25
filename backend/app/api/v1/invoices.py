"""Owned invoice review, issue resolution, and summary-safe mutations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_owned_trip, require_csrf
from app.infrastructure.db.models import Invoice, ReviewIssue, Trip, User
from app.infrastructure.db.session import get_db
from app.schemas import InvoiceBulkUpdate, InvoiceRead, InvoiceUpdate, IssueRead, IssueResolution
from app.services.audit import record_audit
from app.services.invoices import bulk_update_invoices, resolve_issue, serialize_invoice, update_invoice
from app.services.trips import serialize_issue


router = APIRouter(tags=["invoices"])


def _owned_invoice(invoice_id: str, db: Session, user: User) -> Invoice:
    invoice = db.scalar(select(Invoice).join(Trip, Invoice.trip_id == Trip.id).where(Invoice.id == invoice_id, Trip.owner_id == user.id))
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return invoice


@router.get("/trips/{trip_id}/invoices", response_model=list[InvoiceRead])
def list_invoices(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[InvoiceRead]:
    trip = get_owned_trip(trip_id, db, user)
    return [serialize_invoice(item) for item in db.scalars(select(Invoice).where(Invoice.trip_id == trip.id).order_by(Invoice.created_at.desc()))]


@router.patch("/invoices/{invoice_id}", response_model=InvoiceRead, dependencies=[Depends(require_csrf)])
def patch_invoice(invoice_id: str, payload: InvoiceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> InvoiceRead:
    invoice = update_invoice(db, _owned_invoice(invoice_id, db, user), payload)
    record_audit(db, actor_id=user.id, action="INVOICE_UPDATE", resource_type="invoice", resource_id=invoice.id)
    db.commit()
    return serialize_invoice(invoice)


@router.post("/trips/{trip_id}/invoices/bulk-update", response_model=list[InvoiceRead], dependencies=[Depends(require_csrf)])
def bulk_patch_invoices(trip_id: str, payload: InvoiceBulkUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[InvoiceRead]:
    trip = get_owned_trip(trip_id, db, user)
    invoices = bulk_update_invoices(db, trip, payload.invoice_ids, payload.updates)
    record_audit(db, actor_id=user.id, action="INVOICE_BULK_UPDATE", resource_type="trip", resource_id=trip.id)
    db.commit()
    return [serialize_invoice(item) for item in invoices]


@router.get("/trips/{trip_id}/issues", response_model=list[IssueRead])
def list_issues(trip_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[IssueRead]:
    trip = get_owned_trip(trip_id, db, user)
    return [serialize_issue(db, item) for item in db.scalars(select(ReviewIssue).where(ReviewIssue.trip_id == trip.id).order_by(ReviewIssue.created_at.desc()))]


@router.patch("/issues/{issue_id}", response_model=IssueRead, dependencies=[Depends(require_csrf)])
def patch_issue(issue_id: str, payload: IssueResolution, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> IssueRead:
    issue = db.scalar(select(ReviewIssue).join(Trip, ReviewIssue.trip_id == Trip.id).where(ReviewIssue.id == issue_id, Trip.owner_id == user.id))
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    resolution_status = payload.resolution_status
    if resolution_status is None:
        resolution_status = "IGNORED" if payload.ignored else "RESOLVED"
    issue = resolve_issue(db, issue, user.id, resolution_status, payload.resolution_note)
    record_audit(db, actor_id=user.id, action="ISSUE_RESOLVE", resource_type="issue", resource_id=issue.id)
    db.commit()
    return serialize_issue(db, issue)
