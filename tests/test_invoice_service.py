from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from database import Base  # noqa: E402
from models.trip import Trip  # noqa: E402
from models.invoice import Invoice  # noqa: E402
from enums import ReimbursementStatus, ExpenseCategory  # noqa: E402
from services.expense_summary import ExpenseSummary  # noqa: E402
from services.invoice_service import InvoiceService  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def make_trip(db) -> Trip:
    trip = Trip(title="票据服务测试", folder_path="D:/tmp", folder_name="tmp", project_type="DAILY")
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def add_invoice(db, trip: Trip, *, amount: str, role: str = "OFFICIAL_INVOICE") -> Invoice:
    inv = Invoice(
        trip_id=trip.id,
        invoice_type="GENERAL_INVOICE",
        expense_category=ExpenseCategory.OTHER,
        total_amount=Decimal(amount),
        reimbursement_status=ReimbursementStatus.THIS_TRIP,
        include_in_summary=True,
        document_role=role,
        confidence=1.0,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def test_update_invoice_status_already_reimbursed_removes_from_summary(db_session):
    trip = make_trip(db_session)
    invoice = add_invoice(db_session, trip, amount="100.00")

    updated = InvoiceService.update_invoice(
        db_session,
        invoice.id,
        {"reimbursement_status": ReimbursementStatus.ALREADY_REIMBURSED},
    )

    assert updated is not None
    assert updated.reimbursement_status == ReimbursementStatus.ALREADY_REIMBURSED
    assert updated.include_in_summary is False
    summary = ExpenseSummary.compute(db_session, trip)
    assert summary["invoice_total_amount"] == 0.0


def test_update_invoice_status_this_trip_uses_confirmed_amount_in_summary(db_session):
    trip = make_trip(db_session)
    invoice = add_invoice(db_session, trip, amount="100.00")

    updated = InvoiceService.update_invoice(
        db_session,
        invoice.id,
        {"reimbursement_status": ReimbursementStatus.THIS_TRIP, "confirmed_amount": 66.66},
    )

    assert updated is not None
    assert updated.reimbursement_status == ReimbursementStatus.THIS_TRIP
    assert updated.include_in_summary is True
    assert float(updated.confirmed_amount) == 66.66
    summary = ExpenseSummary.compute(db_session, trip)
    assert summary["invoice_total_amount"] == 66.66


def test_bulk_update_pending_status_excludes_all_selected_invoices(db_session):
    trip = make_trip(db_session)
    first = add_invoice(db_session, trip, amount="100.00")
    second = add_invoice(db_session, trip, amount="200.00")

    updated = InvoiceService.bulk_update_invoices(
        db_session,
        trip.id,
        [first.id, second.id],
        {"reimbursement_status": ReimbursementStatus.PENDING},
    )

    assert {inv.id for inv in updated} == {first.id, second.id}
    assert all(inv.reimbursement_status == ReimbursementStatus.PENDING for inv in updated)
    assert all(inv.include_in_summary is False for inv in updated)
    summary = ExpenseSummary.compute(db_session, trip)
    assert summary["invoice_total_amount"] == 0.0


def test_order_screenshot_remains_excluded_even_if_marked_this_trip(db_session):
    trip = make_trip(db_session)
    screenshot = add_invoice(db_session, trip, amount="999.00", role="ORDER_SCREENSHOT")
    screenshot.include_in_summary = False
    db_session.commit()

    updated = InvoiceService.update_invoice(
        db_session,
        screenshot.id,
        {"reimbursement_status": ReimbursementStatus.THIS_TRIP, "include_in_summary": True},
    )

    assert updated is not None
    assert updated.reimbursement_status == ReimbursementStatus.THIS_TRIP
    assert updated.include_in_summary is False
    summary = ExpenseSummary.compute(db_session, trip)
    assert summary["invoice_total_amount"] == 0.0
