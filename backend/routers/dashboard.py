"""Dashboard API – yearly/monthly statistics."""

from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models.trip import Trip
from models.invoice import Invoice
from models.travel_segment import TravelSegment

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class YearlyStatsResponse(BaseModel):
    year: int
    total_project_count: int
    travel_project_count: int
    daily_project_count: int
    total_trip_days: int
    total_invoice_amount: float
    total_allowance_amount: float
    total_with_allowance: float
    reimbursed_amount: float
    unreimbursed_amount: float
    monthly_trends: list[dict]
    category_summary: dict
    city_summary: list[dict]
    reimbursement_summary: dict
    recent_projects: list[dict]


@router.get("/yearly", response_model=YearlyStatsResponse)
def get_yearly_stats(
    year: int = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get yearly dashboard statistics."""
    if year is None:
        year = datetime.now().year

    # All trips in this year (by confirmed or folder dates)
    trips = db.query(Trip).all()
    year_trips = []
    for t in trips:
        d = t.confirmed_start_date or t.folder_date_start or t.inferred_start_date
        if d and d.year == year:
            year_trips.append(t)

    trip_ids = [t.id for t in year_trips]

    # Counts
    travel_count = sum(1 for t in year_trips if t.project_type in ("TRAVEL", None, ""))
    daily_count = sum(1 for t in year_trips if t.project_type == "DAILY")
    total_days = sum(t.trip_days or 0 for t in year_trips)

    # Amounts
    total_invoice = sum(float(t.invoice_total_amount) for t in year_trips)
    total_allowance = sum(float(t.allowance_amount) for t in year_trips)
    total_with = total_invoice + total_allowance

    reimbursed = sum(float(t.grand_total_amount) for t in year_trips if t.reimbursement_status == "REIMBURSED")
    unreimbursed = sum(float(t.grand_total_amount) for t in year_trips if t.reimbursement_status == "NOT_REIMBURSED")

    # Monthly trends
    monthly = []
    for m in range(1, 13):
        mtrips = [t for t in year_trips if (
            (t.confirmed_start_date or t.folder_date_start or t.inferred_start_date)
            and (t.confirmed_start_date or t.folder_date_start or t.inferred_start_date).month == m
        )]
        monthly.append({
            "month": m,
            "project_count": len(mtrips),
            "invoice_amount": sum(float(t.invoice_total_amount) for t in mtrips),
            "allowance_amount": sum(float(t.allowance_amount) for t in mtrips),
        })

    # Category summary
    category = {
        "intercity_transport": sum(float(t.intercity_transport_amount) for t in year_trips),
        "local_transport": sum(float(t.local_transport_amount) for t in year_trips),
        "lodging": sum(float(t.lodging_amount) for t in year_trips),
        "meal": sum(float(t.meal_amount) for t in year_trips),
        "other": sum(float(t.other_amount) for t in year_trips),
    }

    # City summary from travel segments
    if trip_ids:
        segs = db.query(TravelSegment).filter(TravelSegment.trip_id.in_(trip_ids)).all()
    else:
        segs = []
    city_map: dict[str, int] = {}
    for s in segs:
        for city in [s.from_city, s.to_city, s.from_place, s.to_place]:
            if city:
                c = city.replace("站", "").strip()
                if c and len(c) >= 2:
                    city_map[c] = city_map.get(c, 0) + 1
    city_list = sorted(
        [{"city": k, "count": v} for k, v in city_map.items()],
        key=lambda x: -x["count"]
    )[:20]

    # Reimbursement summary
    reimb = {
        "NOT_REIMBURSED": sum(1 for t in year_trips if t.reimbursement_status == "NOT_REIMBURSED"),
        "REIMBURSED": sum(1 for t in year_trips if t.reimbursement_status == "REIMBURSED"),
        "PARTIAL_REIMBURSED": sum(1 for t in year_trips if t.reimbursement_status == "PARTIAL_REIMBURSED"),
        "NOT_REQUIRED": sum(1 for t in year_trips if t.reimbursement_status == "NOT_REQUIRED"),
    }

    # Recent projects
    recent = sorted(year_trips, key=lambda t: t.updated_at or datetime.min, reverse=True)[:10]
    recent_list = [{
        "id": t.id,
        "title": t.title,
        "start_date": str(t.confirmed_start_date or t.folder_date_start or ""),
        "end_date": str(t.confirmed_end_date or t.folder_date_end or ""),
        "route_text": t.route_text or "",
        "document_count": t.document_count,
        "invoice_total_amount": float(t.invoice_total_amount),
        "allowance_amount": float(t.allowance_amount),
        "reimbursement_status": t.reimbursement_status,
        "project_type": t.project_type or "TRAVEL",
    } for t in recent]

    return YearlyStatsResponse(
        year=year,
        total_project_count=len(year_trips),
        travel_project_count=travel_count,
        daily_project_count=daily_count,
        total_trip_days=total_days,
        total_invoice_amount=total_invoice,
        total_allowance_amount=total_allowance,
        total_with_allowance=total_with,
        reimbursed_amount=reimbursed,
        unreimbursed_amount=unreimbursed,
        monthly_trends=monthly,
        category_summary=category,
        city_summary=city_list,
        reimbursement_summary=reimb,
        recent_projects=recent_list,
    )