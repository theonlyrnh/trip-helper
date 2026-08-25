"""Owned annual reporting derived from the Web application's source records."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.reporting.summary import calculate_summary
from app.infrastructure.db.models import Document, Invoice, TravelSegment, Trip, User
from app.schemas import AnnualProjectRead, CitySummaryRead, MonthlyTrendRead, YearlyDashboardRead
from app.services.trips import ordered_route_segments, project_reimbursement_status, route_text_from_segments


ZERO = Decimal("0.00")
_CATEGORY_KEYS = (
    "intercity_transport_amount",
    "local_transport_amount",
    "lodging_amount",
    "meal_amount",
    "refund_change_fee",
    "travel_insurance_amount",
    "other_amount",
)
_REIMBURSEMENT_STATES = (
    "THIS_TRIP",
    "ALREADY_REIMBURSED",
    "PARTIAL_REIMBURSED",
    "NOT_REIMBURSED",
    "PENDING",
)


def yearly_dashboard(db: Session, user: User, selected_year: int | None = None) -> YearlyDashboardRead:
    """Summarize the current user's projects using the same rules as project totals."""
    all_trips = list(db.scalars(select(Trip).where(Trip.owner_id == user.id)))
    dated_trips = [(trip, *_effective_dates(trip)) for trip in all_trips]
    available_years = sorted({start.year for _, start, _ in dated_trips if start} | {date.today().year}, reverse=True)
    year = selected_year or date.today().year
    trips = [(trip, start, end) for trip, start, end in dated_trips if start and start.year == year]
    trip_ids = [trip.id for trip, _, _ in trips]

    invoices_by_trip: dict[str, list[Invoice]] = defaultdict(list)
    segments_by_trip: dict[str, list[TravelSegment]] = defaultdict(list)
    document_counts: dict[str, int] = {}
    if trip_ids:
        for invoice in db.scalars(select(Invoice).where(Invoice.trip_id.in_(trip_ids))):
            invoices_by_trip[invoice.trip_id].append(invoice)
        for segment in db.scalars(select(TravelSegment).where(TravelSegment.trip_id.in_(trip_ids))):
            segments_by_trip[segment.trip_id].append(segment)
        document_counts = dict(
            db.execute(
                select(Document.trip_id, func.count())
                .where(Document.trip_id.in_(trip_ids))
                .group_by(Document.trip_id)
            ).all()
        )

    category_summary = {key: ZERO for key in _CATEGORY_KEYS}
    monthly_trends = [
        {"month": month, "project_count": 0, "invoice_amount": ZERO, "allowance_amount": ZERO}
        for month in range(1, 13)
    ]
    city_counts: Counter[str] = Counter()
    reimbursement_summary = {state: 0 for state in _REIMBURSEMENT_STATES}
    recent_projects: list[AnnualProjectRead] = []
    total_trip_days = 0
    total_invoice_amount = ZERO
    total_allowance_amount = ZERO
    reimbursed_amount = ZERO
    unreimbursed_amount = ZERO

    for trip, start, end in trips:
        invoices = invoices_by_trip[trip.id]
        summary = calculate_summary(trip, invoices)
        invoice_amount = _decimal(summary["invoice_total_amount"])
        allowance_amount = _decimal(summary["allowance_amount"])
        trip_days = int(summary["trip_days"])
        reimbursement_status = project_reimbursement_status(invoices)

        total_trip_days += trip_days
        total_invoice_amount += invoice_amount
        total_allowance_amount += allowance_amount
        reimbursement_summary[reimbursement_status] += 1
        reimbursed_amount += _decimal(summary["reimbursed_total_amount"])
        unreimbursed_amount += _decimal(summary["reimbursement_total_amount"])
        for category in _CATEGORY_KEYS:
            category_summary[category] += _decimal(summary[category])

        month = start.month
        monthly_trends[month - 1]["project_count"] += 1
        monthly_trends[month - 1]["invoice_amount"] += invoice_amount
        monthly_trends[month - 1]["allowance_amount"] += allowance_amount

        segments = segments_by_trip[trip.id]
        previous_stop: str | None = None
        for segment in ordered_route_segments(segments):
            for value in (segment.from_city, segment.to_city):
                if normalized_stop := _normalized_city(value):
                    if normalized_stop != previous_stop:
                        city_counts[normalized_stop] += 1
                    previous_stop = normalized_stop

        recent_projects.append(
            AnnualProjectRead(
                id=trip.id,
                title=trip.title,
                project_type=trip.project_type,
                status=trip.status,
                reimbursement_status=reimbursement_status,
                start_date=start,
                end_date=end,
                route_text=route_text_from_segments(segments) or trip.route_text,
                document_count=document_counts.get(trip.id, 0),
                trip_days=trip_days,
                invoice_total_amount=invoice_amount,
                allowance_amount=allowance_amount,
                grand_total_amount=invoice_amount + allowance_amount,
            )
        )

    recent_projects.sort(key=lambda project: project.start_date or date.min, reverse=True)
    city_summary = [
        CitySummaryRead(city=city, count=count)
        for city, count in sorted(city_counts.items(), key=lambda item: (-item[1], item[0]))[:20]
    ]
    return YearlyDashboardRead(
        year=year,
        available_years=available_years,
        total_project_count=len(trips),
        travel_project_count=sum(1 for trip, _, _ in trips if trip.project_type in {"TRAVEL", "MIXED"}),
        daily_project_count=sum(1 for trip, _, _ in trips if trip.project_type == "DAILY"),
        total_trip_days=total_trip_days,
        total_invoice_amount=total_invoice_amount,
        total_income_amount=total_allowance_amount,
        reimbursed_amount=reimbursed_amount,
        unreimbursed_amount=unreimbursed_amount,
        monthly_trends=[MonthlyTrendRead(**item) for item in monthly_trends],
        category_summary=category_summary,
        city_summary=city_summary,
        reimbursement_summary=reimbursement_summary,
        recent_projects=recent_projects[:20],
    )


def _effective_dates(trip: Trip) -> tuple[date | None, date | None]:
    start = trip.confirmed_start_date or trip.inferred_start_date or trip.input_start_date
    end = trip.confirmed_end_date or trip.inferred_end_date or trip.input_end_date or start
    return start, end


def _decimal(value: Decimal | int) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(value)


def _normalized_city(value: str | None) -> str | None:
    if not value:
        return None
    city = value.strip()
    return city or None
