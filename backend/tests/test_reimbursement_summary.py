from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.reporting.summary import calculate_summary


@dataclass
class TripFixture:
    project_type: str = "TRAVEL"
    trip_days: int | None = 3
    confirmed_start_date: date | None = None
    confirmed_end_date: date | None = None
    daily_allowance: Decimal | None = Decimal("100.00")


@dataclass
class InvoiceFixture:
    reimbursement_status: str
    include_in_summary: bool
    confirmed_amount: Decimal | None
    total_amount: Decimal | None
    expense_category: str
    document_role: str = "OFFICIAL_INVOICE"


def test_project_total_stays_constant_when_the_whole_project_is_reimbursed() -> None:
    trip = TripFixture()
    invoices = [
        InvoiceFixture("THIS_TRIP", True, Decimal("120.00"), Decimal("120.00"), "INTERCITY_TRANSPORT"),
        InvoiceFixture("ALREADY_REIMBURSED", False, Decimal("300.00"), Decimal("300.00"), "LODGING"),
        InvoiceFixture("NOT_REIMBURSED", False, Decimal("80.00"), Decimal("80.00"), "MEAL"),
        InvoiceFixture("THIS_TRIP", False, Decimal("999.00"), Decimal("999.00"), "INTERCITY_TRANSPORT", "ORDER_SCREENSHOT"),
    ]

    before = calculate_summary(trip, invoices)
    assert before["invoice_total_amount"] == Decimal("500.00")
    assert before["allowance_amount"] == Decimal("300.00")
    assert before["grand_total_amount"] == Decimal("800.00")
    assert before["reimbursement_total_amount"] == Decimal("420.00")
    assert before["reimbursed_total_amount"] == Decimal("300.00")
    assert before["unallocated_total_amount"] == Decimal("80.00")
    assert before["grand_total_amount"] == (
        before["reimbursement_total_amount"]
        + before["reimbursed_total_amount"]
        + before["unallocated_total_amount"]
    )

    settled = calculate_summary(
        trip,
        [
            InvoiceFixture("ALREADY_REIMBURSED", False, invoice.confirmed_amount, invoice.total_amount, invoice.expense_category, invoice.document_role)
            for invoice in invoices
        ],
    )
    assert settled["grand_total_amount"] == Decimal("800.00")
    assert settled["reimbursement_total_amount"] == Decimal("0.00")
    assert settled["reimbursed_total_amount"] == Decimal("800.00")
    assert settled["unallocated_total_amount"] == Decimal("0.00")
