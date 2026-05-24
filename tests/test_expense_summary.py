from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

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
from enums import ExpenseCategory, ReimbursementStatus  # noqa: E402
from services.expense_summary import ExpenseSummary  # noqa: E402


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


def make_trip(db, *, project_type: str = "DAILY") -> Trip:
    trip = Trip(title="测试项目", folder_path="D:/tmp", folder_name="tmp", project_type=project_type)
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def add_invoice(
    db,
    trip: Trip,
    *,
    total: str | None,
    confirmed: str | None = None,
    status: str = ReimbursementStatus.THIS_TRIP,
    include: bool = True,
    role: str = "OFFICIAL_INVOICE",
    category: str = ExpenseCategory.OTHER,
) -> Invoice:
    inv = Invoice(
        trip_id=trip.id,
        invoice_type="GENERAL_INVOICE",
        expense_category=category,
        total_amount=Decimal(total) if total is not None else None,
        confirmed_amount=Decimal(confirmed) if confirmed is not None else None,
        reimbursement_status=status,
        include_in_summary=include,
        document_role=role,
        confidence=1.0,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def test_expense_summary_counts_only_this_trip_and_included_invoices(db_session):
    trip = make_trip(db_session)
    add_invoice(db_session, trip, total="100.00", status=ReimbursementStatus.THIS_TRIP, include=True)
    add_invoice(db_session, trip, total="200.00", status=ReimbursementStatus.ALREADY_REIMBURSED, include=True)
    add_invoice(db_session, trip, total="300.00", status=ReimbursementStatus.NOT_REIMBURSED, include=True)
    add_invoice(db_session, trip, total="400.00", status=ReimbursementStatus.PENDING, include=True)
    add_invoice(db_session, trip, total="500.00", status=ReimbursementStatus.THIS_TRIP, include=False)

    summary = ExpenseSummary.compute(db_session, trip)

    assert summary["invoice_total_amount"] == 100.0
    assert summary["grand_total_amount"] == 100.0


def test_expense_summary_prefers_confirmed_amount(db_session):
    trip = make_trip(db_session)
    add_invoice(db_session, trip, total="100.00", confirmed="88.50", category=ExpenseCategory.MEAL)

    summary = ExpenseSummary.compute(db_session, trip)

    assert summary["meal_amount"] == 88.5
    assert summary["invoice_total_amount"] == 88.5


def test_expense_summary_excludes_order_and_booking_screenshots_when_not_included(db_session):
    trip = make_trip(db_session)
    add_invoice(db_session, trip, total="100.00", include=True, role="OFFICIAL_INVOICE")
    add_invoice(db_session, trip, total="1000.00", include=False, role="ORDER_SCREENSHOT")
    add_invoice(db_session, trip, total="2000.00", include=False, role="BOOKING_SCREENSHOT")
    add_invoice(db_session, trip, total="3000.00", include=False, role="SUPPORTING_DOC")

    summary = ExpenseSummary.compute(db_session, trip)

    assert summary["invoice_total_amount"] == 100.0


def test_daily_project_has_no_travel_allowance(db_session):
    trip = make_trip(db_session, project_type="DAILY")
    trip.trip_days = 5
    trip.daily_allowance = Decimal("180.00")
    db_session.commit()
    add_invoice(db_session, trip, total="42.00")

    summary = ExpenseSummary.compute(db_session, trip)

    assert summary["allowance_amount"] == 0.0
    assert summary["grand_total_amount"] == 42.0
