"""Invoice service – invoice-level reimbursement and manual review operations."""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from enums import (
    ExpenseCategory,
    InvoiceType,
    ReimbursementStatus,
    ReviewStatus,
)
from models.invoice import Invoice
from models.lodging_stay import LodgingStay
from models.review_issue import ReviewIssue
from models.travel_segment import TravelSegment
from services.expense_summary import ExpenseSummary
from services.issue_detector import IssueDetector


SUPPORTING_DOCUMENT_ROLES = {
    "ORDER_SCREENSHOT",
    "BOOKING_SCREENSHOT",
    "PAYMENT_PROOF",
    "SUPPORTING_DOC",
    "AUXILIARY_PROOF",
}


INVOICE_UPDATE_FIELDS = {
    "reimbursement_status",
    "include_in_summary",
    "confirmed_amount",
    "review_status",
    "note",
    "expense_category",
    "invoice_type",
    "invoice_code",
    "invoice_number",
    "invoice_date",
    "business_date",
    "seller_name",
    "buyer_name",
    "total_amount",
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
    "document_role",
}


DATE_FIELDS = {
    "invoice_date",
    "business_date",
    "checkin_date",
    "checkout_date",
}

DECIMAL_FIELDS = {
    "confirmed_amount",
    "total_amount",
}

INT_FIELDS = {
    "nights",
}


class InvoiceService:
    """Operations for editable invoice records."""

    @staticmethod
    def list_trip_invoices(db: Session, trip_id: int) -> list[Invoice]:
        """Return all invoices for a trip ordered by id."""
        return (
            db.query(Invoice)
            .filter(Invoice.trip_id == trip_id)
            .order_by(Invoice.id.asc())
            .all()
        )

    @staticmethod
    def get_invoice(db: Session, invoice_id: int) -> Invoice | None:
        """Return one invoice by id."""
        return db.query(Invoice).filter(Invoice.id == invoice_id).first()

    @staticmethod
    def update_invoice(
        db: Session,
        invoice_id: int,
        data: dict[str, Any],
        *,
        refresh_related: bool = True,
    ) -> Invoice | None:
        """Update one invoice and refresh trip-derived summary data."""
        invoice = InvoiceService.get_invoice(db, invoice_id)
        if invoice is None:
            return None

        InvoiceService._apply_update(invoice, data)
        InvoiceService._apply_reimbursement_mapping(invoice, data)

        db.commit()
        db.refresh(invoice)

        if refresh_related:
            InvoiceService.refresh_trip_after_invoice_change(db, invoice.trip_id)
            db.refresh(invoice)

        return invoice

    @staticmethod
    def bulk_update_invoices(
        db: Session,
        trip_id: int,
        invoice_ids: list[int],
        data: dict[str, Any],
    ) -> list[Invoice]:
        """Update multiple invoices in a trip and refresh summary once."""
        if not invoice_ids:
            return []

        invoices = (
            db.query(Invoice)
            .filter(Invoice.trip_id == trip_id, Invoice.id.in_(invoice_ids))
            .order_by(Invoice.id.asc())
            .all()
        )
        for invoice in invoices:
            InvoiceService._apply_update(invoice, data)
            InvoiceService._apply_reimbursement_mapping(invoice, data)

        db.commit()
        for invoice in invoices:
            db.refresh(invoice)

        InvoiceService.refresh_trip_after_invoice_change(db, trip_id)
        for invoice in invoices:
            db.refresh(invoice)
        return invoices

    @staticmethod
    def refresh_trip_after_invoice_change(db: Session, trip_id: int):
        """Refresh derived records, expense summary and unresolved issues."""
        from models.trip import Trip

        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        if trip is None:
            return None

        InvoiceService._rebuild_travel_segments(db, trip_id)
        InvoiceService._rebuild_lodging_stays(db, trip_id)
        ExpenseSummary.update_trip(db, trip)
        IssueDetector.detect_all(db, trip)
        db.refresh(trip)
        return trip

    @staticmethod
    def update_issue(db: Session, issue_id: int, data: dict[str, Any]) -> ReviewIssue | None:
        """Resolve, reopen or ignore one review issue."""
        issue = db.query(ReviewIssue).filter(ReviewIssue.id == issue_id).first()
        if issue is None:
            return None

        ignored = bool(data.get("ignored", False))
        if "resolved" in data:
            issue.resolved = bool(data["resolved"])
        if ignored:
            issue.resolved = True
            if hasattr(issue, "resolution_status"):
                issue.resolution_status = "IGNORED"
        elif issue.resolved:
            if hasattr(issue, "resolution_status"):
                issue.resolution_status = "RESOLVED"
        else:
            if hasattr(issue, "resolution_status"):
                issue.resolution_status = "OPEN"

        if "resolution_status" in data and hasattr(issue, "resolution_status"):
            issue.resolution_status = str(data["resolution_status"] or "OPEN")
            issue.resolved = issue.resolution_status in {"RESOLVED", "IGNORED"}

        if "resolution_note" in data and hasattr(issue, "resolution_note"):
            issue.resolution_note = data["resolution_note"]

        from datetime import datetime

        issue.resolved_at = datetime.now() if issue.resolved else None
        db.commit()
        db.refresh(issue)

        from models.trip import Trip

        trip = db.query(Trip).filter(Trip.id == issue.trip_id).first()
        if trip:
            trip.issue_count = (
                db.query(ReviewIssue)
                .filter(ReviewIssue.trip_id == trip.id, ReviewIssue.resolved == False)
                .count()
            )
            db.commit()

        return issue

    @staticmethod
    def _apply_update(invoice: Invoice, data: dict[str, Any]) -> None:
        for field, value in data.items():
            if field not in INVOICE_UPDATE_FIELDS:
                continue
            setattr(invoice, field, InvoiceService._coerce_field(field, value))

        if data.get("review_status") is None and (
            set(data.keys()) & (INVOICE_UPDATE_FIELDS - {"reimbursement_status", "include_in_summary"})
        ):
            invoice.review_status = ReviewStatus.MANUALLY_CONFIRMED

    @staticmethod
    def _coerce_field(field: str, value: Any) -> Any:
        if value in ("", None):
            return None if field in DATE_FIELDS | DECIMAL_FIELDS | INT_FIELDS else value

        if field in DATE_FIELDS:
            if isinstance(value, date):
                return value
            return date.fromisoformat(str(value)[:10])

        if field in DECIMAL_FIELDS:
            try:
                return Decimal(str(value))
            except (InvalidOperation, ValueError) as exc:
                raise ValueError(f"Invalid decimal value for {field}: {value}") from exc

        if field in INT_FIELDS:
            return int(value)

        if field == "include_in_summary":
            return bool(value)

        return value

    @staticmethod
    def _apply_reimbursement_mapping(invoice: Invoice, data: dict[str, Any]) -> None:
        """Keep reimbursement_status and include_in_summary consistent."""
        role = invoice.document_role or "OFFICIAL_INVOICE"
        is_supporting = role in SUPPORTING_DOCUMENT_ROLES

        if invoice.reimbursement_status != ReimbursementStatus.THIS_TRIP:
            invoice.include_in_summary = False
            return

        if is_supporting:
            invoice.include_in_summary = False
            return

        if "reimbursement_status" in data:
            invoice.include_in_summary = True
        elif "include_in_summary" in data:
            invoice.include_in_summary = bool(data["include_in_summary"])

    @staticmethod
    def _invoice_amount(invoice: Invoice) -> Decimal | None:
        return invoice.confirmed_amount if invoice.confirmed_amount is not None else invoice.total_amount

    @staticmethod
    def _rebuild_travel_segments(db: Session, trip_id: int) -> None:
        invoices = db.query(Invoice).filter(Invoice.trip_id == trip_id).all()
        invoice_by_id = {invoice.id: invoice for invoice in invoices}
        existing = db.query(TravelSegment).filter(TravelSegment.trip_id == trip_id).all()

        for segment in existing:
            invoice = invoice_by_id.get(segment.invoice_id)
            if not invoice or not InvoiceService._is_travel_invoice(invoice):
                db.delete(segment)
                continue
            InvoiceService._copy_invoice_to_segment(invoice, segment)

        existing_invoice_ids = {segment.invoice_id for segment in existing if segment.invoice_id}
        for invoice in invoices:
            if invoice.id not in existing_invoice_ids and InvoiceService._is_travel_invoice(invoice):
                segment = TravelSegment(trip_id=trip_id, invoice_id=invoice.id)
                InvoiceService._copy_invoice_to_segment(invoice, segment)
                db.add(segment)

        db.commit()

    @staticmethod
    def _is_travel_invoice(invoice: Invoice) -> bool:
        return invoice.invoice_type in {
            InvoiceType.TRAIN_TICKET,
            InvoiceType.FLIGHT_TICKET,
            InvoiceType.BUS_TICKET,
            InvoiceType.TAXI_INVOICE,
            InvoiceType.RIDE_HAILING_INVOICE,
            "FLIGHT_TICKET",
            "TRAIN_TICKET",
            "BUS_TICKET",
            "TAXI_INVOICE",
            "RIDE_HAILING_INVOICE",
        } and invoice.expense_category != ExpenseCategory.REFUND_CHANGE_FEE

    @staticmethod
    def _copy_invoice_to_segment(invoice: Invoice, segment: TravelSegment) -> None:
        from datetime import time as dt_time
        import re

        depart_time = None
        if invoice.depart_time_str:
            match = re.match(r"(\d{1,2}):(\d{2})", invoice.depart_time_str)
            if match:
                try:
                    depart_time = dt_time(int(match.group(1)), int(match.group(2)))
                except ValueError:
                    depart_time = None

        segment.transport_type = "FLIGHT" if invoice.invoice_type == InvoiceType.FLIGHT_TICKET else (
            "TRAIN" if invoice.invoice_type == InvoiceType.TRAIN_TICKET else "OTHER"
        )
        segment.depart_date = invoice.flight_date or invoice.business_date
        segment.depart_time = depart_time
        segment.from_city = invoice.from_city
        segment.to_city = invoice.to_city
        segment.from_place = invoice.depart_airport or invoice.from_place
        segment.to_place = invoice.arrive_airport or invoice.to_place
        segment.transport_no = invoice.transport_no
        segment.seat_class = invoice.seat_class or invoice.cabin_class
        segment.amount = InvoiceService._invoice_amount(invoice)
        segment.source_document_id = invoice.document_id
        segment.confidence = invoice.confidence

    @staticmethod
    def _rebuild_lodging_stays(db: Session, trip_id: int) -> None:
        invoices = db.query(Invoice).filter(Invoice.trip_id == trip_id).all()
        invoice_by_id = {invoice.id: invoice for invoice in invoices}
        existing = db.query(LodgingStay).filter(LodgingStay.trip_id == trip_id).all()

        for stay in existing:
            invoice = invoice_by_id.get(stay.invoice_id)
            if not invoice or invoice.invoice_type != InvoiceType.HOTEL_INVOICE:
                db.delete(stay)
                continue
            InvoiceService._copy_invoice_to_stay(invoice, stay)

        existing_invoice_ids = {stay.invoice_id for stay in existing if stay.invoice_id}
        for invoice in invoices:
            if invoice.id not in existing_invoice_ids and invoice.invoice_type == InvoiceType.HOTEL_INVOICE:
                stay = LodgingStay(trip_id=trip_id, invoice_id=invoice.id)
                InvoiceService._copy_invoice_to_stay(invoice, stay)
                db.add(stay)

        db.commit()

    @staticmethod
    def _copy_invoice_to_stay(invoice: Invoice, stay: LodgingStay) -> None:
        stay.hotel_name = invoice.hotel_name or invoice.seller_name
        stay.city = invoice.to_city
        stay.checkin_date = invoice.checkin_date
        stay.checkout_date = invoice.checkout_date
        stay.nights = invoice.nights
        stay.amount = InvoiceService._invoice_amount(invoice)
        stay.source_document_id = invoice.document_id
        stay.confidence = invoice.confidence
