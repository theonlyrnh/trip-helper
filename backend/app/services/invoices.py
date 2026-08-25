"""Invoice review mutations and derived projection refreshes."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.infrastructure.db.models import Invoice, ReviewIssue, Trip
from app.schemas import InvoiceRead, InvoiceUpdate
from app.services.trips import is_reimbursable_invoice, rebuild_trip_projections, refresh_trip_summary


_AUXILIARY_ROLES = {"ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"}
_MANUAL_VALUE_FIELDS = {
    "invoice_type",
    "expense_category",
    "invoice_number",
    "invoice_date",
    "seller_name",
    "buyer_name",
    "total_amount",
    "confirmed_amount",
    "business_date",
    "from_city",
    "to_city",
    "from_place",
    "to_place",
    "transport_no",
    "depart_time_str",
    "seat_class",
    "hotel_name",
    "checkin_date",
    "checkout_date",
    "nights",
    "note",
}
_SUMMARY_ONLY_FIELDS = {"reimbursement_status", "include_in_summary", "review_status"}


def serialize_invoice(invoice: Invoice) -> InvoiceRead:
    return InvoiceRead.model_validate(invoice)


def update_invoice(db: Session, invoice: Invoice, patch: InvoiceUpdate) -> Invoice:
    values = patch.model_dump(exclude_unset=True, exclude={"version"})
    expected_version = patch.version if patch.version is not None else invoice.version
    if expected_version != invoice.version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice was updated by another request")
    final_status = values.get("reimbursement_status", invoice.reimbursement_status)
    final_role = values.get("document_role", invoice.document_role)
    if final_status != "THIS_TRIP" or final_role in _AUXILIARY_ROLES:
        values["include_in_summary"] = False
    elif "include_in_summary" not in values and "reimbursement_status" in values:
        values["include_in_summary"] = True
    if _MANUAL_VALUE_FIELDS.intersection(values) and values.get("review_status", invoice.review_status) == "NEEDS_REVIEW":
        values["review_status"] = "MANUALLY_CONFIRMED"

    # The version predicate is part of the UPDATE itself. Two sessions that
    # read the same version therefore cannot both commit a successful edit.
    result = db.execute(
        update(Invoice)
        .where(Invoice.id == invoice.id, Invoice.version == expected_version)
        .values(**values, version=Invoice.version + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice was updated by another request")
    db.refresh(invoice)
    trip = db.get(Trip, invoice.trip_id)
    if trip:
        if set(values).issubset(_SUMMARY_ONLY_FIELDS):
            refresh_trip_summary(db, trip)
        else:
            rebuild_trip_projections(db, trip)
    db.commit()
    db.refresh(invoice)
    return invoice


def bulk_update_invoices(db: Session, trip: Trip, invoice_ids: list[str], patch: InvoiceUpdate) -> list[Invoice]:
    invoices = list(
        db.scalars(select(Invoice).where(Invoice.trip_id == trip.id, Invoice.id.in_(set(invoice_ids))))
    )
    if len(invoices) != len(set(invoice_ids)):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    values = patch.model_dump(exclude_unset=True, exclude={"version"})
    for invoice in invoices:
        for field, value in values.items():
            setattr(invoice, field, value)
        if invoice.reimbursement_status != "THIS_TRIP" or invoice.document_role in _AUXILIARY_ROLES:
            invoice.include_in_summary = False
        elif "include_in_summary" not in values and (
            "reimbursement_status" in values or "document_role" in values
        ):
            invoice.include_in_summary = True
        if _MANUAL_VALUE_FIELDS.intersection(values) and values.get("review_status", "NEEDS_REVIEW") == "NEEDS_REVIEW":
            invoice.review_status = "MANUALLY_CONFIRMED"
        invoice.version += 1
    if set(values).issubset(_SUMMARY_ONLY_FIELDS):
        refresh_trip_summary(db, trip)
    else:
        rebuild_trip_projections(db, trip)
    db.commit()
    return invoices


def mark_trip_reimbursed(db: Session, trip: Trip) -> int:
    """Mark every reimbursable invoice in a project as already reimbursed.

    Supporting order screenshots remain untouched because they are evidence, not
    reimbursement items. The derived project state consequently stays accurate.
    """
    invoices = list(db.scalars(select(Invoice).where(Invoice.trip_id == trip.id)))
    changed = 0
    for invoice in invoices:
        if not is_reimbursable_invoice(invoice):
            continue
        if invoice.reimbursement_status == "ALREADY_REIMBURSED" and not invoice.include_in_summary:
            continue
        invoice.reimbursement_status = "ALREADY_REIMBURSED"
        invoice.include_in_summary = False
        invoice.version += 1
        changed += 1
    if changed:
        refresh_trip_summary(db, trip)
    db.commit()
    db.refresh(trip)
    return changed


def resolve_issue(db: Session, issue: ReviewIssue, user_id: str, resolution_status: str, note: str | None) -> ReviewIssue:
    from datetime import UTC, datetime

    issue.resolution_status = resolution_status
    issue.resolution_note = note
    issue.resolved_by_id = user_id
    issue.resolved_at = datetime.now(UTC)
    db.commit()
    db.refresh(issue)
    return issue
