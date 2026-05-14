"""Expense summary – aggregates invoice amounts by category and computes allowance."""

from decimal import Decimal
from sqlalchemy.orm import Session

from models.trip import Trip
from models.invoice import Invoice
from enums import ExpenseCategory, ReimbursementStatus


class ExpenseSummary:

    @staticmethod
    def compute(db: Session, trip: Trip) -> dict:
        """
        Compute expense summary for a trip.

        Only counts invoices with reimbursement_status = THIS_TRIP.
        Amount priority: confirmed_amount > total_amount > 0.
        """
        invoices = (
            db.query(Invoice)
            .filter(
                Invoice.trip_id == trip.id,
                Invoice.reimbursement_status == ReimbursementStatus.THIS_TRIP,
                Invoice.include_in_summary == True,
            )
            .all()
        )

        intercity = Decimal("0.00")
        local = Decimal("0.00")
        lodging = Decimal("0.00")
        meal = Decimal("0.00")
        refund_change = Decimal("0.00")
        travel_insurance = Decimal("0.00")
        other = Decimal("0.00")

        for inv in invoices:
            # Use confirmed_amount if set, otherwise total_amount
            # Skip invoices with abnormally large unconfirmed amounts (>100k)
            raw_amount = inv.total_amount or Decimal("0.00")
            if inv.confirmed_amount is not None:
                amount = inv.confirmed_amount
            elif raw_amount > 100000:
                continue
            else:
                amount = raw_amount

            cat = inv.expense_category

            if cat == ExpenseCategory.INTERCITY_TRANSPORT:
                intercity += amount
            elif cat == ExpenseCategory.LOCAL_TRANSPORT:
                local += amount
            elif cat == ExpenseCategory.LODGING:
                lodging += amount
            elif cat == ExpenseCategory.MEAL:
                meal += amount
            elif cat == ExpenseCategory.REFUND_CHANGE_FEE:
                refund_change += amount
            elif cat == ExpenseCategory.TRAVEL_INSURANCE:
                travel_insurance += amount
            else:
                other += amount

        invoice_total = intercity + local + lodging + meal + refund_change + travel_insurance + other
        trip_days = trip.trip_days or trip.confirmed_start_date and trip.confirmed_end_date and (
            (trip.confirmed_end_date - trip.confirmed_start_date).days + 1
        ) or 0

        daily_allowance = trip.daily_allowance or Decimal("180.00")
        allowance_amount = Decimal(str(trip_days)) * daily_allowance
        grand_total = invoice_total + allowance_amount

        return {
            "intercity_transport_amount": float(intercity),
            "local_transport_amount": float(local),
            "lodging_amount": float(lodging),
            "meal_amount": float(meal),
            "refund_change_fee": float(refund_change),
            "travel_insurance_amount": float(travel_insurance),
            "other_amount": float(other),
            "invoice_total_amount": float(invoice_total),
            "trip_days": trip_days,
            "daily_allowance": float(daily_allowance),
            "allowance_amount": float(allowance_amount),
            "grand_total_amount": float(grand_total),
        }

    @staticmethod
    def update_trip(db: Session, trip: Trip) -> Trip:
        """Compute summary and write back to Trip record."""
        summary = ExpenseSummary.compute(db, trip)

        trip.intercity_transport_amount = Decimal(str(summary["intercity_transport_amount"]))
        trip.local_transport_amount = Decimal(str(summary["local_transport_amount"]))
        trip.lodging_amount = Decimal(str(summary["lodging_amount"]))
        trip.meal_amount = Decimal(str(summary["meal_amount"]))
        trip.other_amount = Decimal(str(summary["other_amount"]))
        trip.invoice_total_amount = Decimal(str(summary["invoice_total_amount"]))
        trip.allowance_amount = Decimal(str(summary["allowance_amount"]))
        trip.grand_total_amount = Decimal(str(summary["grand_total_amount"]))

        db.commit()
        db.refresh(trip)
        return trip