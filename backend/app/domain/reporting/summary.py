"""Pure reimbursement calculation retained from the local application's contract."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Protocol


ZERO = Decimal("0.00")


class InvoiceLike(Protocol):
    reimbursement_status: str
    include_in_summary: bool
    document_role: str
    confirmed_amount: Decimal | None
    total_amount: Decimal | None
    expense_category: str


class TripLike(Protocol):
    project_type: str
    trip_days: int | None
    confirmed_start_date: date | None
    confirmed_end_date: date | None
    daily_allowance: Decimal | None


def calculate_trip_days(
    start: date | None,
    end: date | None,
    *,
    include_start_day: bool = True,
    include_end_day: bool = True,
) -> int:
    """Return a non-negative calendar-day count with explicit endpoint rules.

    A same-day trip is one allowance day when either endpoint is enabled. For
    a multi-day interval, the interior days are always counted and each
    enabled endpoint contributes one day. This preserves the historical
    inclusive default while making the two settings observable and testable.
    """
    if start is None or end is None or end < start:
        return 0
    span = (end - start).days
    if span == 0:
        return int(bool(include_start_day or include_end_day))
    return max(0, span - 1 + int(bool(include_start_day)) + int(bool(include_end_day)))


_CATEGORY_KEY = {
    "INTERCITY_TRANSPORT": "intercity_transport_amount",
    "LOCAL_TRANSPORT": "local_transport_amount",
    "LODGING": "lodging_amount",
    "MEAL": "meal_amount",
    "REFUND_CHANGE_FEE": "refund_change_fee",
    "TRAVEL_INSURANCE": "travel_insurance_amount",
}
_AUXILIARY_DOCUMENT_ROLES = {"ORDER_SCREENSHOT", "BOOKING_SCREENSHOT", "SUPPORTING_DOC"}


def calculate_summary(trip: TripLike, invoices: Iterable[InvoiceLike]) -> dict[str, Decimal | int]:
    """Calculate project cost and reimbursement progress without database access.

    Project expense is an immutable financial fact: marking a claim as already
    reimbursed changes its progress, never the cost of the trip.  The response
    therefore carries both project-wide totals and the smaller current claim.
    """
    totals: dict[str, Decimal] = {
        "intercity_transport_amount": ZERO,
        "local_transport_amount": ZERO,
        "lodging_amount": ZERO,
        "meal_amount": ZERO,
        "refund_change_fee": ZERO,
        "travel_insurance_amount": ZERO,
        "other_amount": ZERO,
    }
    reimbursement_invoice_total = ZERO
    reimbursed_invoice_total = ZERO
    reimbursement_statuses: set[str] = set()

    for invoice in invoices:
        if getattr(invoice, "document_role", "OFFICIAL_INVOICE") in _AUXILIARY_DOCUMENT_ROLES:
            continue
        reimbursement_statuses.add(invoice.reimbursement_status)
        amount = _safe_invoice_amount(invoice)
        totals[_CATEGORY_KEY.get(invoice.expense_category, "other_amount")] += amount
        if invoice.reimbursement_status == "THIS_TRIP" and invoice.include_in_summary:
            reimbursement_invoice_total += amount
        elif invoice.reimbursement_status == "ALREADY_REIMBURSED":
            reimbursed_invoice_total += amount

    invoice_total = sum(totals.values(), ZERO)
    raw_trip_days = getattr(trip, "trip_days", None)
    trip_days = max(0, int(raw_trip_days)) if raw_trip_days is not None else 0
    if raw_trip_days is None:
        trip_days = calculate_trip_days(
            getattr(trip, "confirmed_start_date", None),
            getattr(trip, "confirmed_end_date", None),
            include_start_day=getattr(trip, "include_start_day", True),
            include_end_day=getattr(trip, "include_end_day", True),
        )
    raw_allowance = getattr(trip, "daily_allowance", None)
    if raw_allowance is None:
        daily_allowance = Decimal("180.00")
    else:
        try:
            daily_allowance = Decimal(str(raw_allowance))
        except (InvalidOperation, TypeError, ValueError):
            daily_allowance = Decimal("0.00")
        daily_allowance = max(Decimal("0.00"), daily_allowance).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    allowance = ZERO if trip.project_type == "DAILY" else daily_allowance * Decimal(trip_days)
    project_fully_reimbursed = reimbursement_statuses == {"ALREADY_REIMBURSED"}
    allowance_is_current_claim = not reimbursement_statuses or "THIS_TRIP" in reimbursement_statuses
    reimbursement_allowance = allowance if allowance_is_current_claim else ZERO
    reimbursed_allowance = allowance if project_fully_reimbursed else ZERO
    reimbursement_total = reimbursement_invoice_total + reimbursement_allowance
    reimbursed_total = reimbursed_invoice_total + reimbursed_allowance
    return {
        **totals,
        "invoice_total_amount": invoice_total,
        "trip_days": trip_days,
        "daily_allowance": daily_allowance,
        "allowance_amount": allowance,
        "grand_total_amount": invoice_total + allowance,
        "reimbursement_invoice_total_amount": reimbursement_invoice_total,
        "reimbursement_allowance_amount": reimbursement_allowance,
        "reimbursement_total_amount": reimbursement_total,
        "reimbursed_invoice_amount": reimbursed_invoice_total,
        "reimbursed_allowance_amount": reimbursed_allowance,
        "reimbursed_total_amount": reimbursed_total,
        "unallocated_total_amount": max(
            ZERO, invoice_total + allowance - reimbursement_total - reimbursed_total
        ),
    }


def _safe_invoice_amount(invoice: InvoiceLike) -> Decimal:
    raw_amount = invoice.total_amount if invoice.total_amount is not None else ZERO
    amount = invoice.confirmed_amount if invoice.confirmed_amount is not None else raw_amount
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, TypeError, ValueError):
        return ZERO
    if amount < ZERO:
        return ZERO
    if invoice.confirmed_amount is None and amount > Decimal("100000"):
        return ZERO
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
